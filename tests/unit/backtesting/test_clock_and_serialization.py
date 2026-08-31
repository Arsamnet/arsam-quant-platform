"""Deterministic time and canonical identity tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from fx_platform.adapters.clock import FixedClock, SystemClock
from fx_platform.backtesting.clock import BacktestClock
from fx_platform.backtesting.models import ExecutionConfiguration, StrategyConfiguration
from fx_platform.backtesting.serialization import canonical_json, canonical_value, fingerprint

NOW = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)


def test_backtest_clock_is_utc_monotonic_and_deterministic() -> None:
    clock = BacktestClock(NOW)

    assert clock.now() == NOW
    clock.advance_to(NOW)
    clock.advance_to(NOW + timedelta(minutes=1))
    assert clock.now() == NOW + timedelta(minutes=1)

    with pytest.raises(ValueError, match="backward"):
        clock.advance_to(NOW)
    with pytest.raises(ValueError, match="UTC"):
        BacktestClock(NOW.replace(tzinfo=None))


def test_fixed_and_system_clocks_return_aware_utc_values() -> None:
    assert FixedClock(NOW).now() == NOW
    assert SystemClock().now().utcoffset() == timedelta(0)
    with pytest.raises(ValueError, match="UTC"):
        FixedClock(NOW.replace(tzinfo=None))


def test_canonical_serialization_normalizes_order_decimals_and_supported_types() -> None:
    first = {
        "decimal": Decimal("1.1000"),
        "set": frozenset({"b", "a"}),
        "time": NOW,
        "duration": timedelta(seconds=2),
        "uuid": UUID("00000000-0000-4000-8000-000000000001"),
        "sequence": (1, True, None),
    }
    second = dict(reversed(tuple(first.items())))

    assert canonical_json(first) == canonical_json(second)
    assert fingerprint(first) == fingerprint(second)
    assert '"decimal":"1.1"' in canonical_json(first)
    assert canonical_value(Decimal("0.00")) == "0"
    with pytest.raises(ValueError, match="UTC"):
        canonical_json(NOW.replace(tzinfo=None))
    with pytest.raises(TypeError, match="unsupported"):
        canonical_json(object())


def test_configuration_fingerprints_are_stable_and_materially_sensitive() -> None:
    strategy_a = StrategyConfiguration.create(
        strategy_id="fixture",
        strategy_version="1",
        parameters={"volume": Decimal("0.010"), "enabled": True},
    )
    strategy_b = StrategyConfiguration.create(
        strategy_id="fixture",
        strategy_version="1",
        parameters={"enabled": True, "volume": Decimal("0.01")},
    )
    execution = ExecutionConfiguration()

    assert strategy_a.parameter_hash == strategy_b.parameter_hash
    assert strategy_a.parameters == {"enabled": True, "volume": "0.01"}
    assert execution.configuration_hash == ExecutionConfiguration().configuration_hash
    assert (
        execution.configuration_hash
        != ExecutionConfiguration(slippage_ticks=Decimal(0)).configuration_hash
    )


@pytest.mark.parametrize(
    "configuration",
    [
        {"commission_per_lot_per_side": Decimal(-1)},
        {"slippage_ticks": Decimal("NaN")},
        {"spread_handling": "hidden"},
        {"fill_timing": "same_close"},
        {"intra_bar_policy": "optimistic"},
    ],
)
def test_execution_configuration_rejects_unsupported_or_invalid_assumptions(
    configuration: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        ExecutionConfiguration(**configuration)
