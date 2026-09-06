"""Synthetic broker snapshot builders; no values were captured from a broker."""

import json
from pathlib import Path
from typing import Any

from fx_platform.broker_validation import BrokerContractSnapshot, parse_broker_snapshot

FIXTURE_PATH = (
    Path(__file__).parents[2] / "fixtures" / "broker_validation" / "synthetic_eurusd_valid.json"
)
MALFORMED_FIXTURE_PATH = FIXTURE_PATH.with_name("synthetic_malformed.json")


def raw_fixture() -> dict[str, Any]:
    """Return a detached JSON-compatible synthetic fixture."""
    value = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def snapshot_from_raw(value: dict[str, Any]) -> BrokerContractSnapshot:
    return parse_broker_snapshot(json.dumps(value))
