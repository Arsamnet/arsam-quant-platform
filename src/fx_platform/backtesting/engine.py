"""Chronological event-driven backtest orchestration over the real domain pipeline."""

import logging
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid5

from fx_platform import __version__
from fx_platform.adapters.ai import NullAiAdvisor
from fx_platform.adapters.economic import NullEconomicCalendarProvider
from fx_platform.application.ports import StrategyEvaluator, SymbolSpecificationProvider
from fx_platform.backtesting.broker import SimulatedBroker
from fx_platform.backtesting.clock import BacktestClock
from fx_platform.backtesting.conversion import PointInTimeConversionBook
from fx_platform.backtesting.dataset import (
    HistoricalBar,
    HistoricalDataset,
    HistoricalEventStream,
    timeframe_duration,
)
from fx_platform.backtesting.models import (
    AuditEventType,
    BacktestAuditEvent,
    BacktestResult,
    BacktestRunMetadata,
    ExecutionConfiguration,
    StrategyConfiguration,
    risk_configuration_snapshot,
)
from fx_platform.backtesting.portfolio import SimulatedPortfolio
from fx_platform.backtesting.serialization import canonical_json, fingerprint
from fx_platform.domain.common import TradingMode
from fx_platform.domain.execution import ExecutionIntent, OrderType
from fx_platform.domain.market import (
    AccountSnapshot,
    CurrencyConversionRate,
    MarketSnapshot,
    SymbolSpecification,
)
from fx_platform.domain.risk import RiskEngine, RiskLimits
from fx_platform.domain.strategy import SignalCandidate

logger = logging.getLogger(__name__)
_RUN_NAMESPACE = UUID("8f011f54-f6f1-4d90-a967-84240481c802")
_CURRENCY_CODE_LENGTH = 3


class BacktestConfigurationError(ValueError):
    """Fail-closed invalid or incomplete backtest configuration."""


class BacktestEngine:
    """Reuse strategy, advisory, risk, specification, and intent domain boundaries."""

    def __init__(
        self,
        *,
        strategy: StrategyEvaluator,
        strategy_configuration: StrategyConfiguration,
        risk_limits: RiskLimits,
        symbol_specifications: SymbolSpecificationProvider,
        execution_configuration: ExecutionConfiguration,
        account_currency: str = "USD",
        conversion_rates: tuple[CurrencyConversionRate, ...] = (),
    ) -> None:
        if strategy.name != strategy_configuration.strategy_id:
            raise BacktestConfigurationError("strategy ID does not match evaluator")
        if strategy.version != strategy_configuration.strategy_version:
            raise BacktestConfigurationError("strategy version does not match evaluator")
        if (
            len(account_currency) != _CURRENCY_CODE_LENGTH
            or account_currency != account_currency.upper()
        ):
            raise BacktestConfigurationError("account_currency must be an uppercase ISO-style code")
        self._strategy = strategy
        self._strategy_configuration = strategy_configuration
        self._risk_limits = risk_limits
        self._symbol_specifications = symbol_specifications
        self._execution_configuration = execution_configuration
        self._account_currency = account_currency
        self._conversion_rates = conversion_rates
        self._conversion_book = PointInTimeConversionBook(conversion_rates)
        self._risk_engine = RiskEngine(risk_limits)
        self._ai_advisor = NullAiAdvisor()
        self._calendar = NullEconomicCalendarProvider()

    def run(
        self,
        dataset: HistoricalDataset,
        *,
        starting_balance: Decimal,
    ) -> BacktestResult:
        """Process each bar without ever passing future bars to strategy code."""
        specifications = self._required_specifications(dataset)
        risk_snapshot = risk_configuration_snapshot(
            limits=self._risk_limits,
            specifications=tuple(specifications.values()),
            conversion_rates=self._conversion_rates,
        )
        run_id = self._run_id(
            dataset=dataset,
            starting_balance=starting_balance,
            risk_snapshot=risk_snapshot,
        )
        clock = BacktestClock(dataset.metadata.start_at)
        portfolio = SimulatedPortfolio(
            initial_balance=starting_balance,
            account_currency=self._account_currency,
        )
        broker = SimulatedBroker(
            configuration=self._execution_configuration,
            account_currency=self._account_currency,
            max_conversion_age=self._risk_limits.max_conversion_age,
        )
        audit_events: list[BacktestAuditEvent] = []
        previous_closes: dict[str, Decimal] = {}

        for bar_index, bar in enumerate(HistoricalEventStream(dataset)):
            specification = specifications[bar.symbol]
            clock.advance_to(bar.opened_at)
            open_rates = self._conversion_book.available_at(clock.now())
            for fill in broker.fill_pending(
                bar=bar,
                specification=specification,
                conversion_rates=open_rates,
            ):
                if fill.position is None:
                    audit_events.append(
                        self._audit_event(
                            audit_events,
                            AuditEventType.INTENT_REJECTED,
                            clock.now(),
                            bar_index,
                            signal_id=fill.intent.signal_id,
                            risk_decision_id=fill.intent.risk_decision_id,
                            execution_id=fill.intent.execution_id,
                            reasons=(fill.rejection_reason or "unspecified_fill_rejection",),
                        )
                    )
                else:
                    portfolio.open(fill.position)
                    audit_events.append(
                        self._audit_event(
                            audit_events,
                            AuditEventType.ENTRY_FILLED,
                            clock.now(),
                            bar_index,
                            signal_id=fill.position.signal_id,
                            risk_decision_id=fill.position.risk_decision_id,
                            execution_id=fill.position.execution_id,
                        )
                    )

            clock.advance_to(bar.closed_at)
            close_rates = self._conversion_book.available_at(clock.now())
            for trade in broker.exits_for_bar(
                bar=bar,
                positions=portfolio.open_positions,
                specification=specification,
                conversion_rates=close_rates,
            ):
                portfolio.close(trade)
                audit_events.append(
                    self._audit_event(
                        audit_events,
                        AuditEventType.POSITION_CLOSED,
                        clock.now(),
                        bar_index,
                        signal_id=trade.signal_id,
                        risk_decision_id=trade.risk_decision_id,
                        execution_id=trade.execution_id,
                        trade_id=trade.trade_id,
                        reasons=(trade.exit_reason.value,),
                    )
                )

            self._mark_portfolio(
                portfolio=portfolio,
                broker=broker,
                bar=bar,
                specification=specification,
                conversion_rates=close_rates,
            )
            market = self._market_snapshot(
                run_id=run_id,
                bar_index=bar_index,
                bar=bar,
                previous_close=previous_closes.get(bar.symbol, bar.midpoint_close),
            )
            previous_closes[bar.symbol] = bar.midpoint_close
            account = self._account_snapshot(run_id, bar_index, bar, portfolio)
            signal_id = uuid5(run_id, f"bar:{bar_index}:signal")
            strategy_decision = self._strategy.evaluate(
                market,
                signal_id=signal_id,
                evaluated_at=clock.now(),
            )
            if strategy_decision.candidate is None:
                audit_events.append(
                    self._audit_event(
                        audit_events,
                        AuditEventType.NO_SIGNAL,
                        clock.now(),
                        bar_index,
                        reasons=strategy_decision.reasons,
                    )
                )
                continue

            signal = strategy_decision.candidate
            assessment = self._ai_advisor.assess(
                assessment_id=uuid5(run_id, f"bar:{bar_index}:ai"),
                evaluated_at=clock.now(),
                market=market,
                signal=signal,
            )
            calendar = self._calendar.events_for(
                symbol=signal.symbol,
                window_start=clock.now() - self._risk_limits.event_blackout_before,
                window_end=clock.now() + self._risk_limits.event_blackout_after,
            )
            risk_decision_id = uuid5(run_id, f"bar:{bar_index}:risk")
            risk_decision = self._risk_engine.evaluate(
                risk_decision_id=risk_decision_id,
                evaluated_at=clock.now(),
                trading_mode=TradingMode.PAPER,
                market=market,
                account=account,
                signal=signal,
                ai_assessment=assessment,
                economic_events=calendar.events,
                calendar_available=calendar.available,
                symbol_specification=specification,
                conversion_rates=close_rates,
            )
            if not risk_decision.approved:
                audit_events.append(
                    self._audit_event(
                        audit_events,
                        AuditEventType.RISK_REJECTED,
                        clock.now(),
                        bar_index,
                        signal_id=signal.signal_id,
                        risk_decision_id=risk_decision_id,
                        reasons=tuple(reason.value for reason in risk_decision.reasons),
                    )
                )
                continue

            intent = self._intent(
                run_id=run_id,
                dataset=dataset,
                bar_index=bar_index,
                bar=bar,
                signal=signal,
                risk_decision_id=risk_decision_id,
            )
            submission = broker.submit(intent)
            audit_events.append(
                self._audit_event(
                    audit_events,
                    AuditEventType.INTENT_ACCEPTED
                    if submission.accepted
                    else AuditEventType.INTENT_REJECTED,
                    clock.now(),
                    bar_index,
                    signal_id=signal.signal_id,
                    risk_decision_id=risk_decision_id,
                    execution_id=intent.execution_id,
                    reasons=() if submission.reason is None else (submission.reason,),
                )
            )

        metadata = self._metadata(
            run_id=run_id,
            dataset=dataset,
            starting_balance=starting_balance,
            risk_snapshot=risk_snapshot,
        )
        result = BacktestResult(
            metadata=metadata,
            report=portfolio.report(),
            trades=portfolio.closed_trades,
            open_positions=portfolio.open_positions,
            audit_events=tuple(audit_events),
        )
        logger.info(
            "backtest_completed",
            extra={
                "run_id": str(run_id),
                "dataset_id": dataset.metadata.dataset_id,
            },
        )
        return result

    def _required_specifications(
        self,
        dataset: HistoricalDataset,
    ) -> dict[str, SymbolSpecification]:
        if len(dataset.metadata.symbols) != 1:
            raise BacktestConfigurationError(
                "version 0.5.0 backtest runs require exactly one symbol"
            )
        specifications: dict[str, SymbolSpecification] = {}
        for symbol in dataset.metadata.symbols:
            if symbol not in self._risk_limits.allowed_symbols:
                raise BacktestConfigurationError(f"dataset symbol is not risk-allowed: {symbol}")
            specification = self._symbol_specifications.get(symbol)
            if specification is None or specification.symbol != symbol:
                raise BacktestConfigurationError(f"symbol specification unavailable: {symbol}")
            if specification.maximum_spread is None:
                raise BacktestConfigurationError(f"spread policy unavailable: {symbol}")
            specifications[symbol] = specification
        return specifications

    def _run_id(
        self,
        *,
        dataset: HistoricalDataset,
        starting_balance: Decimal,
        risk_snapshot: dict[str, object],
    ) -> UUID:
        identity = {
            "engine_version": __version__,
            "dataset": dataset.metadata.canonical_identity(),
            "strategy_id": self._strategy_configuration.strategy_id,
            "strategy_version": self._strategy_configuration.strategy_version,
            "strategy_parameter_hash": self._strategy_configuration.parameter_hash,
            "risk_configuration_hash": fingerprint(risk_snapshot),
            "execution_configuration_hash": (self._execution_configuration.configuration_hash),
            "starting_balance": starting_balance,
            "account_currency": self._account_currency,
            "random_seed": None,
        }
        return uuid5(_RUN_NAMESPACE, fingerprint(identity))

    def _metadata(
        self,
        *,
        run_id: UUID,
        dataset: HistoricalDataset,
        starting_balance: Decimal,
        risk_snapshot: dict[str, object],
    ) -> BacktestRunMetadata:
        execution_snapshot = self._execution_configuration.canonical_snapshot()
        return BacktestRunMetadata(
            run_id=run_id,
            engine_version=__version__,
            dataset=dataset.metadata,
            strategy=self._strategy_configuration,
            risk_configuration_json=canonical_json(risk_snapshot),
            risk_configuration_hash=fingerprint(risk_snapshot),
            execution_configuration_json=canonical_json(execution_snapshot),
            execution_configuration_hash=fingerprint(execution_snapshot),
            starting_balance=starting_balance,
            account_currency=self._account_currency,
            random_seed=None,
            started_at=dataset.metadata.start_at,
            ended_at=dataset.metadata.end_at,
        )

    @staticmethod
    def _market_snapshot(
        *,
        run_id: UUID,
        bar_index: int,
        bar: HistoricalBar,
        previous_close: Decimal,
    ) -> MarketSnapshot:
        return MarketSnapshot(
            snapshot_id=uuid5(run_id, f"bar:{bar_index}:market"),
            symbol=bar.symbol,
            observed_at=bar.closed_at,
            bid=bar.bid_close,
            ask=bar.ask_close,
            previous_close=previous_close,
        )

    def _account_snapshot(
        self,
        run_id: UUID,
        bar_index: int,
        bar: HistoricalBar,
        portfolio: SimulatedPortfolio,
    ) -> AccountSnapshot:
        if portfolio.balance <= Decimal(0) or portfolio.equity < Decimal(0):
            raise BacktestConfigurationError("portfolio balance is not positive; run failed closed")
        return AccountSnapshot(
            account_id=f"backtest-{run_id}-{bar_index}",
            observed_at=bar.closed_at,
            balance=portfolio.balance,
            equity=portfolio.equity,
            daily_realized_pnl=portfolio.daily_realized_pnl(bar.closed_at),
            open_position_count=len(portfolio.open_positions),
            currency=self._account_currency,
        )

    def _intent(
        self,
        *,
        run_id: UUID,
        dataset: HistoricalDataset,
        bar_index: int,
        bar: HistoricalBar,
        signal: SignalCandidate,
        risk_decision_id: UUID,
    ) -> ExecutionIntent:
        if signal.stop_loss is None:
            raise BacktestConfigurationError("approved backtest signal has no valid stop loss")
        return ExecutionIntent(
            schema_version="1.0",
            execution_id=uuid5(run_id, f"bar:{bar_index}:execution"),
            intent_id=uuid5(run_id, f"bar:{bar_index}:intent"),
            request_id=uuid5(run_id, f"bar:{bar_index}:decision"),
            signal_id=signal.signal_id,
            risk_decision_id=risk_decision_id,
            created_at=bar.closed_at,
            expires_at=dataset.metadata.end_at + timeframe_duration(bar.timeframe),
            node_id="deterministic-backtest",
            symbol=signal.symbol,
            side=signal.side,
            order_type=OrderType.MARKET,
            volume=signal.volume,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            maximum_spread=Decimal("0.00050"),
            risk_fingerprint=uuid5(run_id, f"bar:{bar_index}:risk-fingerprint").hex * 2,
            request_fingerprint=uuid5(run_id, f"bar:{bar_index}:request-fingerprint").hex * 2,
            nonce=f"backtest-{run_id}-{bar_index}",
            strategy_name=signal.strategy_name,
            strategy_version=signal.strategy_version,
            trading_mode=TradingMode.PAPER,
        )

    @staticmethod
    def _mark_portfolio(
        *,
        portfolio: SimulatedPortfolio,
        broker: SimulatedBroker,
        bar: HistoricalBar,
        specification: SymbolSpecification,
        conversion_rates: tuple[CurrencyConversionRate, ...],
    ) -> None:
        values = tuple(
            broker.unrealized_pnl(
                position=position,
                bar=bar,
                specification=specification,
                conversion_rates=conversion_rates,
            )
            for position in portfolio.open_positions
        )
        portfolio.mark_to_market(values)

    @staticmethod
    def _audit_event(
        existing: list[BacktestAuditEvent],
        event_type: AuditEventType,
        occurred_at: datetime,
        bar_index: int,
        *,
        signal_id: UUID | None = None,
        risk_decision_id: UUID | None = None,
        execution_id: UUID | None = None,
        trade_id: UUID | None = None,
        reasons: tuple[str, ...] = (),
    ) -> BacktestAuditEvent:
        event = BacktestAuditEvent(
            sequence=len(existing),
            event_type=event_type,
            occurred_at=occurred_at,
            bar_index=bar_index,
            signal_id=signal_id,
            risk_decision_id=risk_decision_id,
            execution_id=execution_id,
            trade_id=trade_id,
            reasons=reasons,
        )
        logger.debug(
            "backtest_event",
            extra={
                "signal_id": None if signal_id is None else str(signal_id),
                "risk_decision_id": (None if risk_decision_id is None else str(risk_decision_id)),
                "execution_id": None if execution_id is None else str(execution_id),
                "trade_id": None if trade_id is None else str(trade_id),
            },
        )
        return event
