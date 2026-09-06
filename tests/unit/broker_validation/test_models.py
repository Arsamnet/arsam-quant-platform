"""Canonical broker values, mapping, grids, fingerprints, and diff behavior."""

from dataclasses import replace
from decimal import Decimal

import pytest

from fx_platform.broker_validation import (
    BrokerContractDiff,
    BrokerValidationCheck,
    CalculationMode,
    SymbolSpecificationMapper,
    SymbolSpecificationMappingError,
    SymbolTradeMode,
    ValidationSeverity,
    parse_broker_snapshot,
)
from tests.unit.broker_validation.helpers import FIXTURE_PATH, raw_fixture, snapshot_from_raw


def test_canonical_snapshot_preserves_decimal_utc_and_normalized_modes() -> None:
    snapshot = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8"))
    symbol = snapshot.symbol("EURUSD")

    assert symbol is not None
    assert symbol.tick_size == Decimal("0.00001")
    assert symbol.calculation_mode is CalculationMode.FOREX
    assert symbol.trade_mode is SymbolTradeMode.FULL
    assert snapshot.acquired_at.isoformat() == "2026-08-31T10:00:00+00:00"
    assert snapshot.account.account_id_hash is None
    assert "1.1002" in snapshot.to_json()


def test_canonical_round_trip_and_fingerprints_are_deterministic() -> None:
    first = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8"))
    second = parse_broker_snapshot(first.to_json())

    assert first == second
    assert first.snapshot_fingerprint == second.snapshot_fingerprint
    assert first.contract_fingerprint == second.contract_fingerprint
    assert len(first.snapshot_fingerprint) == 64


def test_quote_only_change_changes_full_hash_but_not_contract_hash() -> None:
    first = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8"))
    original = first.symbols[0]
    second = replace(
        first,
        acquired_at=replace(original, bid=Decimal("1.10100")).observed_at,
        symbols=(
            replace(
                original,
                bid=Decimal("1.10100"),
                ask=Decimal("1.10120"),
                observed_at=original.observed_at,
            ),
        ),
    )

    assert first.snapshot_fingerprint != second.snapshot_fingerprint
    assert first.contract_fingerprint == second.contract_fingerprint
    difference = BrokerContractDiff.between(first, second)
    assert not difference.contract_changed
    assert any(change.field.endswith("bid") for change in difference.dynamic_changes)
    assert difference.to_json() == BrokerContractDiff.between(first, second).to_json()


def test_contract_change_is_classified_and_changes_both_hashes() -> None:
    first = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8"))
    second = replace(
        first,
        symbols=(replace(first.symbols[0], contract_size=Decimal(99999)),),
    )
    difference = BrokerContractDiff.between(first, second)

    assert difference.contract_changed
    assert first.contract_fingerprint != second.contract_fingerprint
    assert any(change.field.endswith("contract_size") for change in difference.contract_changes)


def test_logically_unordered_symbol_collections_have_stable_identity() -> None:
    snapshot = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8"))
    eurusd = snapshot.symbols[0]
    gbpusd = replace(eurusd, name="GBPUSD", base_currency="GBP")
    first = replace(
        snapshot,
        requested_symbols=("GBPUSD", "EURUSD"),
        symbols=(gbpusd, eurusd),
        profit_calculations=(),
        margin_calculations=(),
    )
    second = replace(
        first,
        requested_symbols=("EURUSD", "GBPUSD"),
        symbols=(eurusd, gbpusd),
    )

    assert first.snapshot_fingerprint == second.snapshot_fingerprint
    assert first.contract_fingerprint == second.contract_fingerprint
    assert first.to_json() == second.to_json()


def test_symbol_volume_and_price_grids_cover_boundaries() -> None:
    symbol = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8")).symbols[0]

    assert not symbol.accepts_volume(Decimal("0.009"))
    assert symbol.accepts_volume(Decimal("0.01"))
    assert symbol.accepts_volume(Decimal("0.02"))
    assert not symbol.accepts_volume(Decimal("0.015"))
    assert symbol.accepts_volume(Decimal(100))
    assert not symbol.accepts_volume(Decimal("100.01"))
    assert symbol.accepts_price(Decimal("1.10020"))
    assert not symbol.accepts_price(Decimal("1.100205"))
    assert not symbol.accepts_price(Decimal("NaN"))


def test_mapper_creates_broker_derived_domain_specification() -> None:
    symbol = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8")).symbols[0]

    result = SymbolSpecificationMapper().map(symbol, max_spread_ticks=50)

    assert result.symbol == "EURUSD"
    assert result.tick_value_currency == "USD"
    assert result.contract_size == Decimal(100000)
    assert result.accepts_volume(Decimal("0.01"))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"trade_mode": SymbolTradeMode.DISABLED}, "trade-enabled"),
        ({"calculation_mode": CalculationMode.CFD}, "unsupported"),
        ({"tick_value_loss": Decimal("1.01")}, "asymmetric"),
        ({"tick_size": Decimal("0.000015")}, "aligned"),
        ({"quote_currency": "EUR"}, "quote and profit"),
        ({"volume_step": Decimal(0)}, "positive"),
    ],
)
def test_mapper_fails_closed_for_unrepresentable_broker_metadata(
    changes: dict[str, object],
    message: str,
) -> None:
    symbol = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8")).symbols[0]

    with pytest.raises(SymbolSpecificationMappingError, match=message):
        SymbolSpecificationMapper().map(replace(symbol, **changes), max_spread_ticks=50)


def test_snapshot_rejects_duplicate_or_unrequested_symbols() -> None:
    snapshot = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="unique"):
        replace(snapshot, symbols=(snapshot.symbols[0], snapshot.symbols[0]))
    with pytest.raises(ValueError, match="requested"):
        replace(snapshot, requested_symbols=("GBPUSD",))


def test_snapshot_diff_from_raw_contract_fixture() -> None:
    raw = raw_fixture()
    raw["symbols"][0]["tick_size"] = "0.0001"

    changed = snapshot_from_raw(raw)

    assert changed.symbols[0].tick_size == Decimal("0.0001")


@pytest.mark.parametrize(
    "changes",
    [
        {"name": ""},
        {"build": -1},
        {"version": ""},
        {"server_utc_offset_minutes": 2_000},
    ],
)
def test_terminal_snapshot_rejects_invalid_identity(changes: dict[str, object]) -> None:
    terminal = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8")).terminal

    with pytest.raises(ValueError):
        replace(terminal, **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"currency": "usd"},
        {"leverage": 0},
        {"trade_mode_code": -1},
        {"account_id_hash": "not-a-sha256"},
    ],
)
def test_account_snapshot_rejects_invalid_nonsecret_metadata(changes: dict[str, object]) -> None:
    account = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8")).account

    with pytest.raises(ValueError):
        replace(account, **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "eurusd"},
        {"base_currency": "eur"},
        {"point": Decimal(-1)},
        {"swap_long": Decimal("NaN")},
        {"digits": -1},
    ],
)
def test_symbol_snapshot_rejects_malformed_values(changes: dict[str, object]) -> None:
    symbol = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8")).symbols[0]

    with pytest.raises(ValueError):
        replace(symbol, **changes)


@pytest.mark.parametrize(
    ("collection", "changes"),
    [
        ("profit", {"symbol": "eurusd"}),
        ("profit", {"volume": Decimal(-1)}),
        ("profit", {"calculated_profit": Decimal("NaN")}),
        ("profit", {"success": False}),
        ("profit", {"error_code": -1}),
        ("margin", {"symbol": "eurusd"}),
        ("margin", {"calculated_margin": Decimal(-1)}),
        ("margin", {"success": False}),
        ("margin", {"error_code": -1}),
    ],
)
def test_calculation_records_reject_inconsistent_results(
    collection: str,
    changes: dict[str, object],
) -> None:
    snapshot = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8"))
    calculation = (
        snapshot.profit_calculations[0]
        if collection == "profit"
        else snapshot.margin_calculations[0]
    )

    with pytest.raises(ValueError):
        replace(calculation, **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": "2.0"},
        {"mode": "unknown"},
        {"broker_company": ""},
        {"requested_symbols": ()},
        {"requested_symbols": ("eurusd",)},
        {"requested_symbols": ("EURUSD", "EURUSD")},
    ],
)
def test_contract_snapshot_rejects_invalid_identity(changes: dict[str, object]) -> None:
    snapshot = parse_broker_snapshot(FIXTURE_PATH.read_text(encoding="utf-8"))

    with pytest.raises(ValueError):
        replace(snapshot, **changes)


def test_validation_value_objects_reject_empty_audit_fields() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        BrokerValidationCheck(
            code="",
            field="symbol.tick_size",
            severity=ValidationSeverity.BLOCKING,
            expected="known",
            observed=None,
            message="unsafe",
        )
