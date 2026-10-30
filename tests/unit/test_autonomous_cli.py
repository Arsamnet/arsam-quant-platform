"""AI-only autonomous validation tests without broker execution authority."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from fx_platform.autonomous_cli import read_fresh_snapshot, validate_ai_only
from fx_platform.config import AiMode, Settings
from fx_platform.domain.advisory import AiAssessmentStatus
from fx_platform.application.autonomy import AutonomousSnapshotError


class _AiClient:
    def __init__(self) -> None:
        self.calls = 0
        self.payload: Mapping[str, object] | None = None

    def create_assessment(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        self.calls += 1
        self.payload = payload
        return {
            "direction_preference": "sell",
            "confidence": "0.75",
            "market_regime": "trending",
            "uncertainty": "0.25",
            "reasoning_tags": ["validated_snapshot"],
        }


def _payload(now: datetime) -> dict[str, object]:
    bar_time = now.replace(second=0, microsecond=0)
    return {
        "schema_version": "1.0",
        "mode": "autonomous_demo_snapshot",
        "source_type": "mql5_autonomous_probe",
        "acquired_at": now.isoformat(),
        "broker": {
            "company": "FIBO Group, Ltd",
            "server": "FIBOGroup-MT5 Server",
        },
        "terminal": {"connected": True},
        "account": {
            "currency": "USD",
            "trade_mode_code": 0,
            "leverage": 100,
            "margin_mode_code": 2,
            "trade_allowed": True,
            "automated_trading_allowed": True,
            "balance": "9999.73",
            "equity": "9999.73",
            "daily_realized_pnl": "0.21",
            "open_position_count": 0,
        },
        "symbols": [
            {
                "name": "EURUSD",
                "base_currency": "EUR",
                "quote_currency": "USD",
                "bid": "1.11676",
                "ask": "1.11679",
                "previous_close": "1.11760",
                "observed_at": now.isoformat(),
                "decision_bar_time": bar_time.isoformat(),
                "tick_age_seconds": 0,
                "trade_mode_code": 4,
            },
            {
                "name": "GBPUSD",
                "base_currency": "GBP",
                "quote_currency": "USD",
                "bid": "1.33966",
                "ask": "1.33973",
                "previous_close": "1.33739",
                "observed_at": now.isoformat(),
                "decision_bar_time": bar_time.isoformat(),
                "tick_age_seconds": 0,
                "trade_mode_code": 4,
            },
            {
                "name": "USDJPY",
                "base_currency": "USD",
                "quote_currency": "JPY",
                "bid": "157.551",
                "ask": "157.560",
                "previous_close": "157.658",
                "observed_at": now.isoformat(),
                "decision_bar_time": bar_time.isoformat(),
                "tick_age_seconds": 0,
                "trade_mode_code": 4,
            },
        ],
    }


def _settings(snapshot_path: Path, outbox_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        ai_mode=AiMode.OPENAI,
        openai_api_key=SecretStr("test-key"),
        openai_model="configured-model",
        autonomous_snapshot_path=snapshot_path,
        demo_outbox_path=outbox_path,
    )


def test_ai_only_validation_calls_advisor_without_creating_outbox(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    snapshot_path = tmp_path / "snapshot.json"
    outbox_path = tmp_path / "must-not-exist.sqlite3"
    snapshot_path.write_text(json.dumps(_payload(now)), encoding="utf-8")
    settings = _settings(snapshot_path, outbox_path)
    client = _AiClient()

    assessment = validate_ai_only(settings, symbol="EURUSD", ai_client=client)

    assert assessment.status is AiAssessmentStatus.AVAILABLE
    assert assessment.direction_preference is not None
    assert assessment.direction_preference.value == "sell"
    assert assessment.confidence == 0.75
    assert client.calls == 1
    assert client.payload is not None
    assert not outbox_path.exists()


def test_snapshot_validation_rejects_stale_file_before_ai_call(tmp_path: Path) -> None:
    now = datetime.now(UTC) - timedelta(seconds=30)
    snapshot_path = tmp_path / "snapshot.json"
    outbox_path = tmp_path / "must-not-exist.sqlite3"
    snapshot_path.write_text(json.dumps(_payload(now)), encoding="utf-8")
    settings = _settings(snapshot_path, outbox_path)
    client = _AiClient()

    with pytest.raises(AutonomousSnapshotError, match="stale"):
        validate_ai_only(settings, symbol="EURUSD", ai_client=client)

    assert client.calls == 0
    assert not outbox_path.exists()


def test_read_fresh_snapshot_rejects_future_timestamp(tmp_path: Path) -> None:
    now = datetime.now(UTC) + timedelta(seconds=5)
    snapshot_path = tmp_path / "snapshot.json"
    outbox_path = tmp_path / "must-not-exist.sqlite3"
    snapshot_path.write_text(json.dumps(_payload(now)), encoding="utf-8")
    settings = _settings(snapshot_path, outbox_path)

    with pytest.raises(AutonomousSnapshotError, match="future"):
        read_fresh_snapshot(settings)
