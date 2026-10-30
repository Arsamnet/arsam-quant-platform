"""End-to-end deterministic historical simulation over strategy and risk domains."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from fx_platform.adapters.clock import SystemClock
from fx_platform.adapters.market import StaticSymbolSpecificationProvider
from fx_platform.backtesting import (
    AuditEventType,
    BacktestConfigurationError,
    BacktestEngine,
    ExecutionConfiguration,
    ExitReason,
    HistoricalBar,
    HistoricalDataset,
    StrategyConfiguration,
)
from fx_platform.domain.market import MarketSnapshot
from fx_platform.domain.risk import RiskLimits
from fx_platform.domain.strategy import PreviousCloseMomentumStrategy, StrategyDecision
from tests.backtesting_helpers import make_backtest_engine, sample_dataset
from tests.helpers import make_specification


def test_golden_backtest_is_byte_reproducible_with_exact_accounting() -> None:
    dataset = sample_dataset()
    engine = make_backtest_engine()

    first = engine.run(dataset, starting_balance=Decimal(10000))
    second = engine.run(dataset, starting_balance=Decimal("10000.00"))

    assert first == second
    assert first.to_json() == second.to_json()
    assert first.metadata.dataset.checksum == (
        "42ef6f69d7ab7dd1febb1b2d392410365eb8d90dfb756d9c86ef41a9b0b7d1ac"
    )
    assert str(first.metadata.run_id) == "1be4454c-9692-5156-a884-901ba35b5070"
    assert first.metadata.strategy.parameter_hash == (
        "4437c4443d23b959f97d9230fdf833859ecf0ecd95cc81de344d070e6da642c0"
    )
    assert first.metadata.risk_configuration_hash == (
        "42e116a2f45f4bf26860f62a35a2ee804769191131d6826b41c2cff371133861"
    )
    assert first.metadata.execution_configuration_hash == (
        "2e6a081fb9c073fcc4d37d5de1cb42cbf3ac8eb1a015b95866133f27dfcd7b53"
    )
    assert first.report.final_balance == Decimal("9998.91")
    assert first.report.net_pnl == Decimal("-1.09")
    assert first.report.maximum_drawdown == Decimal("1.09")
    assert first.report.transaction_costs == Decimal("0.29")
    assert first.report.trade_count == 1
    assert first.report.profit_factor == Decimal(0)
    assert first.report.payoff_ratio is None
    trade = first.trades[0]
    assert str(trade.trade_id) == "4f4248f2-32b2-5fa3-b4ef-9b8f450101cd"
    assert trade.exit_reason is ExitReason.STOP_LOSS
    assert trade.executed_entry_price == Decimal("1.10121")
    assert trade.exit_price == Decimal("1.10019")
    assert trade.gross_pnl == Decimal("-0.8")
    assert trade.spread_cost == Decimal("0.2")
    assert trade.slippage_cost == Decimal("0.02")
    assert trade.commission == Decimal("0.07")
    assert trade.swap_cost == Decimal(0)
    assert trade.net_pnl == Decimal("-1.09")


def test_signal_fills_only_at_next_bar_open_and_conflict_is_adverse_first() -> None:
    result = make_backtest_engine().run(sample_dataset(), starting_balance=Decimal(10000))
    accepted = next(
        event for event in result.audit_events if event.event_type is AuditEventType.INTENT_ACCEPTED
    )
    filled = next(
        event for event in result.audit_events if event.event_type is AuditEventType.ENTRY_FILLED
    )
    closed = next(
        event for event in result.audit_events if event.event_type is AuditEventType.POSITION_CLOSED
    )

    assert accepted.bar_index == 1
    assert filled.bar_index == 2
    assert result.trades[0].opened_at == sample_dataset().bars[2].opened_at
    assert closed.reasons == ("stop_loss",)
    assert sample_dataset().bars[2].bid_high >= result.trades[0].take_profit
    assert sample_dataset().bars[2].bid_low <= result.trades[0].stop_loss


def test_positive_costs_cannot_improve_same_trade_path() -> None:
    dataset = sample_dataset()
    zero_cost = make_backtest_engine(
        commission=Decimal(0),
        slippage_ticks=Decimal(0),
    ).run(dataset, starting_balance=Decimal(10000))
    positive_cost = make_backtest_engine().run(dataset, starting_balance=Decimal(10000))

    assert tuple(trade.exit_reason for trade in zero_cost.trades) == tuple(
        trade.exit_reason for trade in positive_cost.trades
    )
    assert positive_cost.report.net_pnl <= zero_cost.report.net_pnl
    assert positive_cost.report.transaction_costs > zero_cost.report.transaction_costs


@dataclass(slots=True)
class _FutureLeakGuardStrategy:
    name: str = "future_leak_guard"
    version: str = "1.0.0"
    observed: list[tuple[datetime, Decimal]] = field(default_factory=list)

    def evaluate(
        self,
        market: MarketSnapshot,
        symbol_specification,
        *,
        signal_id,
        evaluated_at,
    ) -> StrategyDecision:
        del signal_id
        assert symbol_specification.symbol == market.symbol
        self.observed.append((evaluated_at, market.previous_close))
        return StrategyDecision(
            strategy_name=self.name,
            strategy_version=self.version,
            evaluated_at=evaluated_at,
            candidate=None,
            reasons=("guard_no_signal",),
        )


def test_strategy_receives_only_current_and_previous_data_not_future_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def wall_clock_forbidden(self: SystemClock) -> datetime:
        del self
        raise AssertionError("wall clock leaked into backtest")

    monkeypatch.setattr(SystemClock, "now", wall_clock_forbidden)
    strategy = _FutureLeakGuardStrategy()
    engine = BacktestEngine(
        strategy=strategy,
        strategy_configuration=StrategyConfiguration.create(
            strategy_id=strategy.name,
            strategy_version=strategy.version,
            parameters={},
        ),
        risk_limits=RiskLimits(allowed_symbols=frozenset({"EURUSD"})),
        symbol_specifications=StaticSymbolSpecificationProvider((make_specification(),)),
        execution_configuration=ExecutionConfiguration(),
    )

    engine.run(sample_dataset(), starting_balance=Decimal(10000))

    assert strategy.observed[0] == (
        datetime(2026, 1, 5, 12, 1, tzinfo=UTC),
        Decimal("1.1001"),
    )
    assert strategy.observed[1][1] == Decimal("1.1001")
    assert strategy.observed[1][1] != sample_dataset().bars[2].midpoint_close
    assert tuple(item[0] for item in strategy.observed) == tuple(
        bar.closed_at for bar in sample_dataset().bars
    )


def test_risk_rejection_never_reaches_simulated_execution() -> None:
    result = make_backtest_engine(
        risk_limits=RiskLimits(
            allowed_symbols=frozenset({"EURUSD"}),
            max_volume=Decimal("0.001"),
        )
    ).run(sample_dataset(), starting_balance=Decimal(10000))

    rejected = tuple(
        event for event in result.audit_events if event.event_type is AuditEventType.RISK_REJECTED
    )
    assert rejected
    assert "volume_limit_exceeded" in rejected[0].reasons
    assert not any(event.event_type is AuditEventType.ENTRY_FILLED for event in result.audit_events)
    assert result.trades == ()


def test_missing_symbol_specification_fails_before_simulation() -> None:
    strategy = _FutureLeakGuardStrategy()
    engine = BacktestEngine(
        strategy=strategy,
        strategy_configuration=StrategyConfiguration.create(
            strategy_id=strategy.name,
            strategy_version=strategy.version,
            parameters={},
        ),
        risk_limits=RiskLimits(allowed_symbols=frozenset({"EURUSD"})),
        symbol_specifications=StaticSymbolSpecificationProvider(
            (make_specification(symbol="GBPUSD", base_currency="GBP"),)
        ),
        execution_configuration=ExecutionConfiguration(),
    )

    with pytest.raises(BacktestConfigurationError, match="specification unavailable"):
        engine.run(sample_dataset(), starting_balance=Decimal(10000))


def test_cross_currency_data_without_directed_rate_fails_closed_in_risk() -> None:
    bars = tuple(
        HistoricalBar(
            symbol="USDJPY",
            timeframe="M1",
            opened_at=datetime(2026, 1, 5, 12, minute, tzinfo=UTC),
            bid_open=Decimal("150.000"),
            bid_high=Decimal("150.200"),
            bid_low=Decimal("149.900"),
            bid_close=Decimal("150.000") if minute == 0 else Decimal("150.100"),
            spread=Decimal("0.010"),
        )
        for minute in range(3)
    )
    dataset = HistoricalDataset.create(
        dataset_id="usdjpy",
        dataset_version="1",
        source="synthetic",
        bars=bars,
    )
    strategy = PreviousCloseMomentumStrategy()
    engine = BacktestEngine(
        strategy=strategy,
        strategy_configuration=StrategyConfiguration.create(
            strategy_id=strategy.name,
            strategy_version=strategy.version,
            parameters={
                "volume": strategy.volume,
                "stop_distance_ticks": strategy.stop_distance_ticks,
                "reward_to_risk": strategy.reward_to_risk,
            },
        ),
        risk_limits=RiskLimits(allowed_symbols=frozenset({"USDJPY"})),
        symbol_specifications=StaticSymbolSpecificationProvider(
            (
                make_specification(
                    symbol="USDJPY",
                    base_currency="USD",
                    quote_currency="JPY",
                    tick_size=Decimal("0.001"),
                    tick_value=Decimal(100),
                    tick_value_currency="JPY",
                ),
            )
        ),
        execution_configuration=ExecutionConfiguration(),
    )

    result = engine.run(dataset, starting_balance=Decimal(10000))

    reasons = tuple(reason for event in result.audit_events for reason in event.reasons)
    assert "conversion_rate_unavailable" in reasons
    assert result.trades == ()


def test_fill_time_spread_change_rejects_pending_intent() -> None:
    dataset = sample_dataset()
    bars = list(dataset.bars)
    bars[2] = HistoricalBar(
        symbol="EURUSD",
        timeframe="M1",
        opened_at=bars[2].opened_at,
        bid_open=bars[2].bid_open,
        bid_high=bars[2].bid_high,
        bid_low=bars[2].bid_low,
        bid_close=bars[2].bid_close,
        spread=Decimal("0.001"),
    )
    changed = HistoricalDataset.create(
        dataset_id="fill-spread-change",
        dataset_version="1",
        source="synthetic",
        bars=tuple(bars),
    )

    result = make_backtest_engine().run(changed, starting_balance=Decimal(10000))

    rejected = tuple(
        event for event in result.audit_events if event.event_type is AuditEventType.INTENT_REJECTED
    )
    assert rejected[0].reasons == ("spread_too_wide_at_fill",)
    assert result.trades == ()


def test_engine_constructor_and_required_metadata_fail_closed() -> None:
    strategy = _FutureLeakGuardStrategy()
    specification = make_specification()
    provider = StaticSymbolSpecificationProvider((specification,))
    limits = RiskLimits(allowed_symbols=frozenset({"EURUSD"}))
    valid_configuration = StrategyConfiguration.create(
        strategy_id=strategy.name,
        strategy_version=strategy.version,
        parameters={},
    )

    with pytest.raises(BacktestConfigurationError, match="strategy ID"):
        BacktestEngine(
            strategy=strategy,
            strategy_configuration=StrategyConfiguration.create(
                strategy_id="other",
                strategy_version=strategy.version,
                parameters={},
            ),
            risk_limits=limits,
            symbol_specifications=provider,
            execution_configuration=ExecutionConfiguration(),
        )
    with pytest.raises(BacktestConfigurationError, match="strategy version"):
        BacktestEngine(
            strategy=strategy,
            strategy_configuration=StrategyConfiguration.create(
                strategy_id=strategy.name,
                strategy_version="2",
                parameters={},
            ),
            risk_limits=limits,
            symbol_specifications=provider,
            execution_configuration=ExecutionConfiguration(),
        )
    with pytest.raises(BacktestConfigurationError, match="account_currency"):
        BacktestEngine(
            strategy=strategy,
            strategy_configuration=valid_configuration,
            risk_limits=limits,
            symbol_specifications=provider,
            execution_configuration=ExecutionConfiguration(),
            account_currency="usd",
        )

    not_allowed = BacktestEngine(
        strategy=strategy,
        strategy_configuration=valid_configuration,
        risk_limits=RiskLimits(allowed_symbols=frozenset({"GBPUSD"})),
        symbol_specifications=StaticSymbolSpecificationProvider(
            (make_specification(symbol="GBPUSD", base_currency="GBP"),)
        ),
        execution_configuration=ExecutionConfiguration(),
    )
    with pytest.raises(BacktestConfigurationError, match="not risk-allowed"):
        not_allowed.run(sample_dataset(), starting_balance=Decimal(10000))

    missing_spread = BacktestEngine(
        strategy=strategy,
        strategy_configuration=valid_configuration,
        risk_limits=limits,
        symbol_specifications=StaticSymbolSpecificationProvider(
            (replace(specification, max_spread_ticks=None),)
        ),
        execution_configuration=ExecutionConfiguration(),
    )
    with pytest.raises(BacktestConfigurationError, match="spread policy"):
        missing_spread.run(sample_dataset(), starting_balance=Decimal(10000))


def test_engine_rejects_multi_symbol_dataset_in_initial_scope() -> None:
    dataset = sample_dataset()
    second_symbol = replace(
        dataset.bars[-1],
        symbol="GBPUSD",
        opened_at=dataset.bars[-1].closed_at,
    )
    multi_symbol = HistoricalDataset.create(
        dataset_id="multi",
        dataset_version="1",
        source="synthetic",
        bars=(*dataset.bars, second_symbol),
    )
    strategy = _FutureLeakGuardStrategy()
    engine = BacktestEngine(
        strategy=strategy,
        strategy_configuration=StrategyConfiguration.create(
            strategy_id=strategy.name,
            strategy_version=strategy.version,
            parameters={},
        ),
        risk_limits=RiskLimits(allowed_symbols=frozenset({"EURUSD", "GBPUSD"})),
        symbol_specifications=StaticSymbolSpecificationProvider(
            (
                make_specification(),
                make_specification(symbol="GBPUSD", base_currency="GBP"),
            )
        ),
        execution_configuration=ExecutionConfiguration(),
    )

    with pytest.raises(BacktestConfigurationError, match="exactly one symbol"):
        engine.run(multi_symbol, starting_balance=Decimal(10000))


def test_nonpositive_portfolio_state_fails_closed_before_new_decision() -> None:
    limits = RiskLimits(
        allowed_symbols=frozenset({"EURUSD"}),
        max_trade_risk_fraction=Decimal(1),
        max_daily_loss_absolute_cap=None,
    )

    with pytest.raises(BacktestConfigurationError, match="portfolio balance"):
        make_backtest_engine(risk_limits=limits).run(
            sample_dataset(),
            starting_balance=Decimal("1.01"),
        )


def test_risk_fingerprint_changes_when_material_limit_changes() -> None:
    first = make_backtest_engine(
        risk_limits=RiskLimits(
            allowed_symbols=frozenset({"EURUSD"}),
            max_volume=Decimal("0.10"),
        )
    ).run(sample_dataset(), starting_balance=Decimal(10000))
    second = make_backtest_engine(
        risk_limits=RiskLimits(
            allowed_symbols=frozenset({"EURUSD"}),
            max_volume=Decimal("0.09"),
        )
    ).run(sample_dataset(), starting_balance=Decimal(10000))

    assert first.metadata.risk_configuration_hash != second.metadata.risk_configuration_hash
    assert first.metadata.run_id != second.metadata.run_id
