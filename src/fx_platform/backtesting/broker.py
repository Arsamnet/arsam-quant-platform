"""Deterministic no-network simulated broker adapter."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from fx_platform.backtesting.dataset import HistoricalBar
from fx_platform.backtesting.models import (
    ExecutionConfiguration,
    ExitReason,
    SimulatedPosition,
    TradeRecord,
)
from fx_platform.domain.common import TradeSide
from fx_platform.domain.execution import ExecutionIntent
from fx_platform.domain.market import (
    CurrencyConversionRate,
    SymbolSpecification,
    convert_currency,
)


class BacktestExecutionError(RuntimeError):
    """A required simulated execution or accounting input was unavailable."""


@dataclass(frozen=True, slots=True, kw_only=True)
class IntentSubmission:
    """Immediate deterministic acceptance or rejection by the simulated adapter."""

    intent: ExecutionIntent
    accepted: bool
    reason: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class EntryFillOutcome:
    """A pending intent either filled or failed closed at the next symbol bar."""

    intent: ExecutionIntent
    position: SimulatedPosition | None
    rejection_reason: str | None


class SimulatedBroker:
    """Queue risk-approved paper intents and fill them without any external system."""

    def __init__(
        self,
        *,
        configuration: ExecutionConfiguration,
        account_currency: str,
        max_conversion_age: timedelta,
    ) -> None:
        self._configuration = configuration
        self._account_currency = account_currency
        self._max_conversion_age = max_conversion_age
        self._pending: dict[UUID, ExecutionIntent] = {}
        self._seen: set[UUID] = set()

    @property
    def pending_intents(self) -> tuple[ExecutionIntent, ...]:
        return tuple(self._pending.values())

    def submit(self, intent: ExecutionIntent) -> IntentSubmission:
        """Accept each paper execution ID once; duplicate IDs are rejected."""
        if intent.execution_id in self._seen:
            return IntentSubmission(intent=intent, accepted=False, reason="duplicate_execution_id")
        self._seen.add(intent.execution_id)
        self._pending[intent.execution_id] = intent
        return IntentSubmission(intent=intent, accepted=True, reason=None)

    def fill_pending(
        self,
        *,
        bar: HistoricalBar,
        specification: SymbolSpecification,
        conversion_rates: tuple[CurrencyConversionRate, ...],
    ) -> tuple[EntryFillOutcome, ...]:
        """Fill matching pending intents at this bar open using adverse slippage."""
        matching = tuple(intent for intent in self._pending.values() if intent.symbol == bar.symbol)
        outcomes: list[EntryFillOutcome] = []
        for intent in matching:
            del self._pending[intent.execution_id]
            reason = self._entry_rejection_reason(intent, bar, specification)
            if reason is not None:
                outcomes.append(
                    EntryFillOutcome(intent=intent, position=None, rejection_reason=reason)
                )
                continue
            outcomes.append(
                EntryFillOutcome(
                    intent=intent,
                    position=self._open_position(
                        intent=intent,
                        bar=bar,
                        specification=specification,
                        conversion_rates=conversion_rates,
                    ),
                    rejection_reason=None,
                )
            )
        return tuple(outcomes)

    def exits_for_bar(
        self,
        *,
        bar: HistoricalBar,
        positions: tuple[SimulatedPosition, ...],
        specification: SymbolSpecification,
        conversion_rates: tuple[CurrencyConversionRate, ...],
    ) -> tuple[TradeRecord, ...]:
        """Resolve SL/TP touches; a simultaneous touch always chooses stop loss."""
        trades: list[TradeRecord] = []
        for position in positions:
            if position.symbol != bar.symbol:
                continue
            exit_reason = self._exit_reason(position, bar)
            if exit_reason is None:
                continue
            trades.append(
                self._close_trade(
                    position=position,
                    bar=bar,
                    exit_reason=exit_reason,
                    specification=specification,
                    conversion_rates=conversion_rates,
                )
            )
        return tuple(trades)

    def unrealized_pnl(
        self,
        *,
        position: SimulatedPosition,
        bar: HistoricalBar,
        specification: SymbolSpecification,
        conversion_rates: tuple[CurrencyConversionRate, ...],
    ) -> Decimal:
        """Estimate liquidation value at bar close including exit slippage and commission."""
        slippage = self._configuration.slippage_ticks * specification.tick_size
        if position.side is TradeSide.BUY:
            exit_price = bar.bid_close - slippage
            direction = Decimal(1)
        else:
            exit_price = bar.ask_close + slippage
            direction = Decimal(-1)
        quote_pnl = (
            direction
            * (exit_price - position.executed_entry_price)
            * specification.contract_size
            * position.volume
        )
        converted = self._convert_signed(
            quote_pnl,
            source_currency=specification.quote_currency,
            rates=conversion_rates,
            evaluated_at=bar.closed_at,
        )
        exit_commission = self._configuration.commission_per_lot_per_side * position.volume
        return converted - exit_commission

    def _entry_rejection_reason(
        self,
        intent: ExecutionIntent,
        bar: HistoricalBar,
        specification: SymbolSpecification,
    ) -> str | None:
        reason: str | None = None
        if bar.opened_at >= intent.expires_at:
            reason = "execution_intent_expired"
        elif specification.maximum_spread is None:
            reason = "spread_policy_unavailable"
        elif bar.spread > specification.maximum_spread:
            reason = "spread_too_wide_at_fill"
        slippage = self._configuration.slippage_ticks * specification.tick_size
        filled_entry = (
            bar.ask_open + slippage if intent.side is TradeSide.BUY else bar.bid_open - slippage
        )
        if reason is None and filled_entry <= Decimal(0):
            reason = "invalid_filled_entry"
        elif reason is None and (
            (intent.side is TradeSide.BUY and intent.stop_loss >= filled_entry)
            or (intent.side is TradeSide.SELL and intent.stop_loss <= filled_entry)
        ):
            reason = "stop_invalid_at_fill"
        elif (
            reason is None
            and intent.take_profit is not None
            and (
                (intent.side is TradeSide.BUY and intent.take_profit <= filled_entry)
                or (intent.side is TradeSide.SELL and intent.take_profit >= filled_entry)
            )
        ):
            reason = "take_profit_invalid_at_fill"
        return reason

    def _open_position(
        self,
        *,
        intent: ExecutionIntent,
        bar: HistoricalBar,
        specification: SymbolSpecification,
        conversion_rates: tuple[CurrencyConversionRate, ...],
    ) -> SimulatedPosition:
        slippage = self._configuration.slippage_ticks * specification.tick_size
        executed_entry = (
            bar.ask_open + slippage if intent.side is TradeSide.BUY else bar.bid_open - slippage
        )
        half_spread_quote = bar.spread / Decimal(2) * specification.contract_size * intent.volume
        slippage_quote = slippage * specification.contract_size * intent.volume
        return SimulatedPosition(
            position_id=uuid5(intent.execution_id, "position"),
            execution_id=intent.execution_id,
            signal_id=intent.signal_id,
            risk_decision_id=intent.risk_decision_id,
            symbol=intent.symbol,
            side=intent.side,
            volume=intent.volume,
            requested_entry_price=intent.entry_price,
            reference_entry_price=bar.midpoint_open,
            executed_entry_price=executed_entry,
            stop_loss=intent.stop_loss,
            take_profit=intent.take_profit,
            opened_at=bar.opened_at,
            entry_spread_cost=self._convert_nonnegative(
                half_spread_quote,
                source_currency=specification.quote_currency,
                rates=conversion_rates,
                evaluated_at=bar.opened_at,
            ),
            entry_commission=self._configuration.commission_per_lot_per_side * intent.volume,
            entry_slippage_cost=self._convert_nonnegative(
                slippage_quote,
                source_currency=specification.quote_currency,
                rates=conversion_rates,
                evaluated_at=bar.opened_at,
            ),
        )

    @staticmethod
    def _exit_reason(position: SimulatedPosition, bar: HistoricalBar) -> ExitReason | None:
        if position.side is TradeSide.BUY:
            stop_touched = bar.bid_low <= position.stop_loss
            target_touched = (
                position.take_profit is not None and bar.bid_high >= position.take_profit
            )
        else:
            stop_touched = bar.ask_high >= position.stop_loss
            target_touched = (
                position.take_profit is not None and bar.ask_low <= position.take_profit
            )
        if stop_touched:
            return ExitReason.STOP_LOSS
        if target_touched:
            return ExitReason.TAKE_PROFIT
        return None

    def _close_trade(
        self,
        *,
        position: SimulatedPosition,
        bar: HistoricalBar,
        exit_reason: ExitReason,
        specification: SymbolSpecification,
        conversion_rates: tuple[CurrencyConversionRate, ...],
    ) -> TradeRecord:
        baseline_exit = self._baseline_exit(position, bar, exit_reason)
        slippage = self._configuration.slippage_ticks * specification.tick_size
        direction = Decimal(1) if position.side is TradeSide.BUY else Decimal(-1)
        executed_exit = baseline_exit - slippage if direction > 0 else baseline_exit + slippage
        if executed_exit <= Decimal(0):
            raise BacktestExecutionError("deterministic exit price is not positive")
        reference_exit = (
            baseline_exit + (bar.spread / Decimal(2))
            if position.side is TradeSide.BUY
            else baseline_exit - (bar.spread / Decimal(2))
        )
        gross_quote = (
            direction
            * (reference_exit - position.reference_entry_price)
            * specification.contract_size
            * position.volume
        )
        exit_spread_quote = bar.spread / Decimal(2) * specification.contract_size * position.volume
        exit_slippage_quote = slippage * specification.contract_size * position.volume
        gross_pnl = self._convert_signed(
            gross_quote,
            source_currency=specification.quote_currency,
            rates=conversion_rates,
            evaluated_at=bar.closed_at,
        )
        spread_cost = position.entry_spread_cost + self._convert_nonnegative(
            exit_spread_quote,
            source_currency=specification.quote_currency,
            rates=conversion_rates,
            evaluated_at=bar.closed_at,
        )
        slippage_cost = position.entry_slippage_cost + self._convert_nonnegative(
            exit_slippage_quote,
            source_currency=specification.quote_currency,
            rates=conversion_rates,
            evaluated_at=bar.closed_at,
        )
        commission = position.entry_commission + (
            self._configuration.commission_per_lot_per_side * position.volume
        )
        swap_cost = Decimal(0)
        net_pnl = gross_pnl - spread_cost - commission - slippage_cost - swap_cost
        return TradeRecord(
            trade_id=uuid5(position.position_id, "trade"),
            position_id=position.position_id,
            signal_id=position.signal_id,
            risk_decision_id=position.risk_decision_id,
            execution_id=position.execution_id,
            symbol=position.symbol,
            side=position.side,
            volume=position.volume,
            requested_entry_price=position.requested_entry_price,
            executed_entry_price=position.executed_entry_price,
            exit_price=executed_exit,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            opened_at=position.opened_at,
            closed_at=bar.closed_at,
            exit_reason=exit_reason,
            gross_pnl=gross_pnl,
            spread_cost=spread_cost,
            commission=commission,
            slippage_cost=slippage_cost,
            swap_cost=swap_cost,
            net_pnl=net_pnl,
        )

    @staticmethod
    def _baseline_exit(
        position: SimulatedPosition,
        bar: HistoricalBar,
        exit_reason: ExitReason,
    ) -> Decimal:
        if exit_reason is ExitReason.TAKE_PROFIT:
            if position.take_profit is None:
                raise BacktestExecutionError("take-profit exit has no configured target")
            return position.take_profit
        if position.side is TradeSide.BUY:
            return min(position.stop_loss, bar.bid_open)
        return max(position.stop_loss, bar.ask_open)

    def _convert_nonnegative(
        self,
        amount: Decimal,
        *,
        source_currency: str,
        rates: tuple[CurrencyConversionRate, ...],
        evaluated_at: datetime,
    ) -> Decimal:
        if amount == Decimal(0):
            return Decimal(0)
        return self._convert_positive(
            amount,
            source_currency=source_currency,
            rates=rates,
            evaluated_at=evaluated_at,
        )

    def _convert_signed(
        self,
        amount: Decimal,
        *,
        source_currency: str,
        rates: tuple[CurrencyConversionRate, ...],
        evaluated_at: datetime,
    ) -> Decimal:
        if amount == Decimal(0):
            return Decimal(0)
        direction = Decimal(1) if amount > Decimal(0) else Decimal(-1)
        return direction * self._convert_positive(
            abs(amount),
            source_currency=source_currency,
            rates=rates,
            evaluated_at=evaluated_at,
        )

    def _convert_positive(
        self,
        amount: Decimal,
        *,
        source_currency: str,
        rates: tuple[CurrencyConversionRate, ...],
        evaluated_at: datetime,
    ) -> Decimal:
        result = convert_currency(
            amount=amount,
            source_currency=source_currency,
            target_currency=self._account_currency,
            conversion_rates=rates,
            evaluated_at=evaluated_at,
            max_conversion_age=self._max_conversion_age,
            max_future_skew=timedelta(0),
        )
        if result.failure is not None or result.amount is None:
            reason = "unknown" if result.failure is None else result.failure.value
            raise BacktestExecutionError(f"currency conversion failed closed: {reason}")
        return result.amount
