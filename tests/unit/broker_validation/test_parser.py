"""Strict schema, numeric, enum, bitmask, timestamp, and tamper parsing tests."""

import json
from pathlib import Path

import pytest

from fx_platform.broker_validation import (
    BrokerSnapshotParseError,
    CalculationMode,
    ExpirationMode,
    FillingMode,
    OrderMode,
    decode_expiration_modes,
    decode_filling_modes,
    decode_order_modes,
    load_broker_snapshot,
    parse_broker_snapshot,
)
from tests.unit.broker_validation.helpers import (
    FIXTURE_PATH,
    MALFORMED_FIXTURE_PATH,
    raw_fixture,
    snapshot_from_raw,
)


def test_bitmask_decoding_preserves_unknown_bits() -> None:
    orders, order_unknown = decode_order_modes(127 | 128)
    fills, fill_unknown = decode_filling_modes(3 | 8)
    expirations, expiration_unknown = decode_expiration_modes(15 | 16)

    assert orders == frozenset(OrderMode)
    assert order_unknown == 128
    assert fills == frozenset({FillingMode.FOK, FillingMode.IOC})
    assert fill_unknown == 8
    assert expirations == frozenset(ExpirationMode)
    assert expiration_unknown == 16
    with pytest.raises(BrokerSnapshotParseError, match="non-negative"):
        decode_order_modes(-1)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.pop("account"), "missing fields"),
        (lambda value: value.update({"unexpected": True}), "unknown fields"),
        (lambda value: value["symbols"][0].update({"tick_size": 0.00001}), "decimal string"),
        (lambda value: value["symbols"][0].update({"tick_size": "NaN"}), "finite"),
        (lambda value: value.update({"acquired_at": "2026-08-31T10:00:00"}), "UTC offset"),
        (lambda value: value["profit_calculations"][0].update({"side": "hold"}), "unknown enum"),
        (lambda value: value["terminal"].update({"connected": 1}), "boolean"),
        (lambda value: value["symbols"][0].update({"digits": True}), "integer"),
        (lambda value: value.update({"schema_version": "2.0"}), "unsupported"),
        (lambda value: value.update({"mode": "trade"}), "safety mode"),
        (lambda value: value.update({"source_type": "unknown"}), "source_type"),
        (lambda value: value.update({"broker": []}), "must be an object"),
        (lambda value: value.update({"symbols": {}}), "must be an array"),
        (lambda value: value["broker"].update({"company": ""}), "non-empty text"),
        (lambda value: value["account"].update({"leverage": -1}), "must not be negative"),
        (
            lambda value: value["terminal"].update({"server_utc_offset_minutes": "zero"}),
            "integer or null",
        ),
        (lambda value: value["symbols"][0].update({"tick_size": "abc"}), "malformed"),
        (lambda value: value.update({"acquired_at": "not-time"}), "invalid timestamp"),
        (
            lambda value: value["profit_calculations"][0].update({"success": False}),
            "successful profit",
        ),
        (
            lambda value: value["margin_calculations"][0].update({"calculated_margin": "-1"}),
            "must not be negative",
        ),
        (
            lambda value: value["margin_calculations"][0].update({"side": "hold"}),
            "unknown enum",
        ),
    ],
)
def test_parser_rejects_malformed_or_unknown_required_structure(mutation, message: str) -> None:
    raw = raw_fixture()
    mutation(raw)

    with pytest.raises(BrokerSnapshotParseError, match=message):
        snapshot_from_raw(raw)


def test_parser_rejects_duplicate_json_keys_and_malformed_fixture() -> None:
    with pytest.raises(BrokerSnapshotParseError, match="duplicate"):
        parse_broker_snapshot('{"schema_version":"1.0","schema_version":"1.0"}')
    with pytest.raises(BrokerSnapshotParseError):
        load_broker_snapshot(MALFORMED_FIXTURE_PATH)


def test_unknown_numeric_calculation_mode_is_preserved_for_fail_closed_validation() -> None:
    raw = raw_fixture()
    raw["symbols"][0]["calculation_mode_code"] = 999

    snapshot = snapshot_from_raw(raw)

    assert snapshot.symbols[0].calculation_mode is CalculationMode.UNKNOWN
    assert snapshot.symbols[0].calculation_mode_code == 999


def test_aware_timestamp_offsets_are_normalized_without_server_timezone_inference() -> None:
    raw = raw_fixture()
    raw["acquired_at"] = "2026-08-31T13:30:00+03:30"

    snapshot = snapshot_from_raw(raw)

    assert snapshot.acquired_at.isoformat() == "2026-08-31T10:00:00+00:00"
    assert snapshot.terminal.server_utc_offset_minutes is None


def test_expected_fingerprint_detects_tampered_snapshot(tmp_path: Path) -> None:
    original = load_broker_snapshot(FIXTURE_PATH)
    tampered = raw_fixture()
    tampered["symbols"][0]["contract_size"] = "99999"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(BrokerSnapshotParseError, match="fingerprint"):
        load_broker_snapshot(path, expected_fingerprint=original.snapshot_fingerprint)


def test_loader_rejects_missing_non_utf8_and_oversized_files(tmp_path: Path) -> None:
    with pytest.raises(BrokerSnapshotParseError, match="cannot read"):
        load_broker_snapshot(tmp_path / "missing.json")
    binary = tmp_path / "binary.json"
    binary.write_bytes(b"\xff\xfe")
    with pytest.raises(BrokerSnapshotParseError, match="cannot read"):
        load_broker_snapshot(binary)
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * 1_000_001)
    with pytest.raises(BrokerSnapshotParseError, match="one-megabyte"):
        load_broker_snapshot(oversized)
