"""Immutable backtest configuration, position, ledger, and audit invariants."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from fx_platform.backtesting.models import (
    AuditEventType,
    BacktestAuditEvent,
    ExitReason,
    SimulatedPosition,
    StrategyConfiguration,
    TradeRecord,
)
from fx_platform.backtesting.serialization import fingerprint
from fx_platform.domain.common import TradeSide
from tests.backtesting_helpers import make_backtest_engine, sample_dataset

NOW = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)


def _position(**changes: object) -> SimulatedPosition:
    values: dict[str, object] = {
        "position_id": uuid4(),
        "execution_id": uuid4(),
        "signal_id": uuid4(),
        "risk_decision_id": uuid4(),
        "symbol": "EURUSD",
        "side": TradeSide.BUY,
        "volume": Decimal("0.01"),
        "requested_entry_price": Decimal("1.1"),
        "reference_entry_price": Decimal("1.1"),
        "executed_entry_price": Decimal("1.1001"),
        "stop_loss": Decimal("1.09"),
        "take_profit": Decimal("1.11"),
        "opened_at": NOW,
        "entry_spread_cost": Decimal("0.1"),
        "entry_commission": Decimal("0.035"),
        "entry_slippage_cost": Decimal("0.01"),
    }
    values.update(changes)
    return SimulatedPosition(**values)


def _trade(**changes: object) -> TradeRecord:
    position = _position()
    values: dict[str, object] = {
        "trade_id": uuid4(),
        "position_id": position.position_id,
        "signal_id": position.signal_id,
        "risk_decision_id": position.risk_decision_id,
        "execution_id": position.execution_id,
        "symbol": position.symbol,
        "side": position.side,
        "volume": position.volume,
        "requested_entry_price": position.requested_entry_price,
        "executed_entry_price": position.executed_entry_price,
        "exit_price": Decimal("1.101"),
        "stop_loss": position.stop_loss,
        "take_profit": position.take_profit,
        "opened_at": position.opened_at,
        "closed_at": NOW + timedelta(minutes=1),
        "exit_reason": ExitReason.TAKE_PROFIT,
        "gross_pnl": Decimal(1),
        "spread_cost": Decimal("0.2"),
        "commission": Decimal("0.07"),
        "slippage_cost": Decimal("0.02"),
        "swap_cost": Decimal(0),
        "net_pnl": Decimal("0.71"),
    }
    values.update(changes)
    return TradeRecord(**values)


def test_strategy_configuration_rejects_invalid_or_noncanonical_snapshots() -> None:
    with pytest.raises(ValueError, match="identity"):
        StrategyConfiguration.create(strategy_id="", strategy_version="1", parameters={})
    with pytest.raises(ValueError, match="canonical"):
        StrategyConfiguration(
            strategy_id="fixture",
            strategy_version="1",
            parameter_snapshot_json='{ "value": 1 }',
            parameter_hash=fingerprint({"value": 1}),
        )
    with pytest.raises(ValueError, match="hash"):
        StrategyConfiguration(
            strategy_id="fixture",
            strategy_version="1",
            parameter_snapshot_json='{"value":1}',
            parameter_hash="0" * 64,
        )
    non_object = StrategyConfiguration(
        strategy_id="fixture",
        strategy_version="1",
        parameter_snapshot_json="[]",
        parameter_hash=fingerprint([]),
    )
    with pytest.raises(ValueError, match="object"):
        _ = non_object.parameters


@pytest.mark.parametrize(
    "changes",
    [
        {"volume": Decimal(0)},
        {"take_profit": Decimal(0)},
        {"entry_spread_cost": Decimal(-1)},
        {"entry_commission": Decimal("NaN")},
    ],
)
def test_position_rejects_invalid_financial_state(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _position(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"closed_at": NOW - timedelta(seconds=1)},
        {"volume": Decimal(0)},
        {"gross_pnl": Decimal("NaN")},
        {"spread_cost": Decimal(-1)},
        {"net_pnl": Decimal(99)},
    ],
)
def test_trade_ledger_rejects_invalid_or_inconsistent_accounting(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        _trade(**changes)


def test_audit_event_rejects_negative_sequence_or_bar_index() -> None:
    with pytest.raises(ValueError, match="negative"):
        BacktestAuditEvent(
            sequence=-1,
            event_type=AuditEventType.NO_SIGNAL,
            occurred_at=NOW,
            bar_index=0,
        )


def test_open_positions_are_included_in_canonical_result_serialization() -> None:
    dataset = sample_dataset()
    bars = list(dataset.bars)
    bars[2] = replace(
        bars[2],
        bid_high=Decimal("1.1020"),
        bid_low=Decimal("1.1005"),
    )
    open_dataset = type(dataset).create(
        dataset_id=dataset.metadata.dataset_id,
        dataset_version=dataset.metadata.dataset_version,
        source=dataset.metadata.source,
        bars=tuple(bars[:3]),
    )

    result = make_backtest_engine().run(open_dataset, starting_balance=Decimal(10000))

    assert len(result.open_positions) == 1
    assert result.report.open_position_count == 1
    assert result.to_dict()["open_positions"]
    assert '"status":"open"' in result.to_json()
