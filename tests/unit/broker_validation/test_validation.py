"""Blocking policy, warnings, freshness, tolerances, and report determinism."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from fx_platform.adapters.market import bootstrap_symbol_specifications
from fx_platform.broker_validation import (
    AccountPositionMode,
    AccountTradeMode,
    BrokerContractValidator,
    BrokerReadiness,
    CalculationMode,
    ValidationOverallStatus,
    ValidationPolicy,
    ValidationSeverity,
    parse_broker_snapshot,
)
from tests.unit.broker_validation.helpers import FIXTURE_PATH

NOW = datetime(2026, 8, 31, 10, 0, tzinfo=UTC)


def _snapshot():
    return parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8"))


def _expected():
    result = bootstrap_symbol_specifications(frozenset({"EURUSD"})).get("EURUSD")
    assert result is not None
    return result


def _report(*, snapshot=None, policy=None, as_of: datetime = NOW):
    effective_policy = policy or ValidationPolicy(
        expected_broker_company="SYNTHETIC TEST BROKER - NOT FIBOGROUP DATA",
        expected_broker_server="SYNTHETIC-DEMO - NOT BROKER CALIBRATED",
    )
    return BrokerContractValidator().validate(
        expected=_expected(),
        snapshot=snapshot or _snapshot(),
        symbol="EURUSD",
        policy=effective_policy,
        as_of=as_of,
    )


def _check(report, code: str):
    return next(check for check in report.checks if check.code == code)


def test_valid_synthetic_hedging_fx_contract_passes_deterministically() -> None:
    first = _report()
    second = _report()

    assert first.overall_status is ValidationOverallStatus.PASS
    assert first.readiness is BrokerReadiness.READY
    assert first.to_json() == second.to_json()
    assert _check(first, "profit_calibration").severity is ValidationSeverity.PASS
    assert _check(first, "stop_freeze_levels_captured").severity is ValidationSeverity.INFO


@pytest.mark.parametrize(
    ("symbol_changes", "code"),
    [
        ({"tick_size": Decimal("0.0001")}, "tick_size"),
        ({"contract_size": Decimal(99999)}, "contract_size"),
        ({"volume_step": Decimal("0.1")}, "volume_step"),
        (
            {"calculation_mode": CalculationMode.CFD, "calculation_mode_code": 3},
            "calculation_mode_supported",
        ),
        ({"base_currency": "GBP"}, "base_currency"),
        ({"profit_currency": "EUR"}, "profit_currency"),
        ({"volume_min": Decimal("0.02")}, "volume_minimum"),
        ({"volume_max": Decimal("0.05")}, "volume_maximum"),
        ({"volume_limit": Decimal("0.05")}, "volume_limit"),
        ({"order_mode_unknown_bits": 128}, "unknown_order_mode_bits"),
    ],
)
def test_material_symbol_mismatches_are_blocking(
    symbol_changes: dict[str, object],
    code: str,
) -> None:
    snapshot = _snapshot()
    changed = replace(snapshot, symbols=(replace(snapshot.symbols[0], **symbol_changes),))

    report = _report(snapshot=changed)

    assert report.overall_status is ValidationOverallStatus.BLOCKING_MISMATCH
    assert report.readiness is BrokerReadiness.NOT_READY
    assert _check(report, code).severity is ValidationSeverity.BLOCKING


def test_netting_wrong_currency_and_non_demo_account_are_blocking() -> None:
    snapshot = _snapshot()
    account = replace(
        snapshot.account,
        currency="EUR",
        position_mode=AccountPositionMode.RETAIL_NETTING,
        margin_mode_code=0,
        trade_mode=AccountTradeMode.REAL,
        trade_mode_code=2,
    )

    report = _report(snapshot=replace(snapshot, account=account))

    assert _check(report, "account_currency").severity is ValidationSeverity.BLOCKING
    assert _check(report, "account_position_mode").severity is ValidationSeverity.BLOCKING
    assert _check(report, "account_trade_mode").severity is ValidationSeverity.BLOCKING


def test_missing_symbol_produces_unknown_readiness() -> None:
    snapshot = _snapshot()

    report = _report(snapshot=replace(snapshot, symbols=()))

    assert report.readiness is BrokerReadiness.UNKNOWN
    assert _check(report, "symbol_unavailable").severity is ValidationSeverity.BLOCKING


@pytest.mark.parametrize(
    ("as_of", "code"),
    [
        (NOW + timedelta(minutes=5, microseconds=1), "snapshot_stale"),
        (NOW - timedelta(seconds=3), "snapshot_from_future"),
    ],
)
def test_snapshot_freshness_fails_closed(as_of: datetime, code: str) -> None:
    report = _report(as_of=as_of)

    assert _check(report, code).severity is ValidationSeverity.BLOCKING


def test_symbol_observation_has_independent_freshness() -> None:
    snapshot = _snapshot()
    symbol = replace(snapshot.symbols[0], observed_at=NOW - timedelta(minutes=6))

    report = _report(snapshot=replace(snapshot, symbols=(symbol,)))

    assert _check(report, "symbol_observation_stale").severity is ValidationSeverity.BLOCKING


def test_explicit_broker_identity_mismatch_is_blocking() -> None:
    policy = ValidationPolicy(
        expected_broker_company="Expected Company",
        expected_broker_server="Expected-Server",
    )

    report = _report(policy=policy)

    assert _check(report, "broker_company").severity is ValidationSeverity.BLOCKING
    assert _check(report, "broker_server").severity is ValidationSeverity.BLOCKING


def test_unpinned_broker_identity_fails_closed() -> None:
    report = _report(policy=ValidationPolicy())

    assert _check(report, "broker_company_unpinned").severity is ValidationSeverity.BLOCKING
    assert _check(report, "broker_server_unpinned").severity is ValidationSeverity.BLOCKING
    assert report.readiness is BrokerReadiness.NOT_READY


def test_dynamic_spread_and_tick_values_are_warnings_not_contract_truth() -> None:
    snapshot = _snapshot()
    symbol = replace(
        snapshot.symbols[0],
        ask=Decimal("1.10100"),
        reported_spread_points=100,
        tick_value=Decimal("1.02"),
        tick_value_profit=Decimal("1.02"),
        tick_value_loss=Decimal("1.02"),
    )

    report = _report(snapshot=replace(snapshot, symbols=(symbol,)))

    assert report.overall_status is ValidationOverallStatus.WARNING
    assert _check(report, "observed_spread").severity is ValidationSeverity.WARNING
    assert _check(report, "tick_value").severity is ValidationSeverity.WARNING


def test_conservative_volume_bounds_and_missing_spread_policy_are_explicit() -> None:
    snapshot = _snapshot()
    symbol = replace(
        snapshot.symbols[0],
        volume_min=Decimal("0.001"),
        volume_max=Decimal("0.10"),
    )
    expected = replace(_expected(), max_spread_ticks=None)

    report = BrokerContractValidator().validate(
        expected=expected,
        snapshot=replace(snapshot, symbols=(symbol,)),
        symbol="EURUSD",
        policy=ValidationPolicy(),
        as_of=NOW,
    )

    assert _check(report, "volume_minimum").severity is ValidationSeverity.WARNING
    assert _check(report, "volume_maximum").severity is ValidationSeverity.PASS
    assert _check(report, "spread_policy_unavailable").severity is ValidationSeverity.BLOCKING


def test_invalid_quote_and_unknown_modes_fail_closed() -> None:
    snapshot = _snapshot()
    symbol = replace(
        snapshot.symbols[0],
        bid=Decimal("1.2"),
        ask=Decimal("1.1"),
        filling_modes=frozenset(),
        filling_mode_unknown_bits=8,
    )

    report = _report(snapshot=replace(snapshot, symbols=(symbol,)))

    assert _check(report, "quote_order").severity is ValidationSeverity.BLOCKING
    assert _check(report, "filling_mode_available").severity is ValidationSeverity.BLOCKING
    assert _check(report, "unknown_filling_mode_bits").severity is ValidationSeverity.BLOCKING


def test_missing_calibration_warns_and_margin_never_changes_risk_engine() -> None:
    snapshot = replace(_snapshot(), profit_calculations=(), margin_calculations=())

    report = _report(snapshot=snapshot)

    assert report.overall_status is ValidationOverallStatus.WARNING
    assert _check(report, "profit_calibration_missing").severity is ValidationSeverity.WARNING
    assert _check(report, "margin_calibration_captured").severity is ValidationSeverity.INFO


def test_profit_calibration_beyond_tolerance_is_blocking() -> None:
    snapshot = _snapshot()
    calculation = replace(snapshot.profit_calculations[0], calculated_profit=Decimal("0.03"))
    changed = replace(
        snapshot,
        profit_calculations=(calculation, snapshot.profit_calculations[1]),
    )

    report = _report(snapshot=changed)

    profit_checks = tuple(check for check in report.checks if check.code == "profit_calibration")
    assert any(check.severity is ValidationSeverity.BLOCKING for check in profit_checks)


def test_failed_profit_calculation_warns_without_fabricating_value() -> None:
    snapshot = _snapshot()
    failed = replace(
        snapshot.profit_calculations[0],
        success=False,
        calculated_profit=None,
        error_code=4302,
    )

    report = _report(
        snapshot=replace(
            snapshot,
            profit_calculations=(failed, snapshot.profit_calculations[1]),
        )
    )

    assert _check(report, "profit_calculation_failed").severity is ValidationSeverity.WARNING


def test_relative_money_tolerance_can_pass_above_absolute_tolerance() -> None:
    snapshot = _snapshot()
    calculation = replace(snapshot.profit_calculations[0], calculated_profit=Decimal("0.011"))
    policy = ValidationPolicy(
        absolute_money_tolerance=Decimal(0),
        relative_money_tolerance=Decimal("0.10"),
    )

    report = _report(
        snapshot=replace(
            snapshot,
            profit_calculations=(calculation, snapshot.profit_calculations[1]),
        ),
        policy=policy,
    )

    assert _check(report, "profit_calibration").severity is ValidationSeverity.PASS


def test_money_tolerance_boundary_is_inclusive_and_fingerprinted() -> None:
    snapshot = _snapshot()
    calculation = replace(snapshot.profit_calculations[0], calculated_profit=Decimal("0.02"))
    changed = replace(
        snapshot,
        profit_calculations=(calculation, snapshot.profit_calculations[1]),
    )
    policy = ValidationPolicy(absolute_money_tolerance=Decimal("0.01"))

    report = _report(snapshot=changed, policy=policy)

    assert _check(report, "profit_calibration").severity is ValidationSeverity.PASS
    assert report.policy_fingerprint == policy.policy_fingerprint


def test_cross_currency_profit_case_is_explicitly_uncompared() -> None:
    snapshot = _snapshot()
    symbol = replace(snapshot.symbols[0], profit_currency="JPY")

    report = _report(snapshot=replace(snapshot, symbols=(symbol,)))

    assert (
        _check(report, "profit_calibration_conversion_required").severity is ValidationSeverity.INFO
    )


@pytest.mark.parametrize(
    "policy",
    [
        ValidationPolicy(maximum_snapshot_age=timedelta(0)),
        ValidationPolicy(relative_money_tolerance=Decimal(0)),
        ValidationPolicy(price_tolerance_ticks=Decimal("0.5")),
    ],
)
def test_valid_tolerance_policy_variants_are_stable(policy: ValidationPolicy) -> None:
    assert len(policy.policy_fingerprint) == 64


@pytest.mark.parametrize(
    "changes",
    [
        {"expected_account_currency": "usd"},
        {"maximum_snapshot_age": timedelta(seconds=-1)},
        {"absolute_money_tolerance": Decimal("NaN")},
        {"relative_money_tolerance": Decimal(-1)},
        {"supported_calculation_modes": frozenset()},
        {"expected_broker_company": ""},
    ],
)
def test_invalid_tolerance_policy_fails_closed(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ValidationPolicy(**changes)


def test_validation_requires_matching_expected_symbol_and_utc_as_of() -> None:
    validator = BrokerContractValidator()

    with pytest.raises(ValueError, match="does not match"):
        validator.validate(
            expected=_expected(),
            snapshot=_snapshot(),
            symbol="GBPUSD",
            policy=ValidationPolicy(),
            as_of=NOW,
        )
    with pytest.raises(ValueError, match="UTC"):
        _report(as_of=NOW.replace(tzinfo=None))
