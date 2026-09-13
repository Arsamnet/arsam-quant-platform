"""Authenticated localhost demo execution transport integration tests."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from fx_platform.api.main import create_app
from fx_platform.config import Settings
from fx_platform.domain.common import TradingMode

pytestmark = pytest.mark.anyio

_SECRET = "demo-api-test-secret-that-is-at-least-32-chars"
_MAX_MQL5_ULONG = 18_446_744_073_709_551_615


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        trading_mode=TradingMode.DEMO,
        demo_execution_enabled=True,
        demo_execution_secret=SecretStr(_SECRET),
        demo_outbox_path=path,
    )


def _decision_payload() -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    return {
        "schema_version": "1.0",
        "request_id": str(uuid4()),
        "timestamp": now,
        "nonce": f"nonce_{uuid4().hex}",
        "node_id": "local-demo-node",
        "market": {
            "snapshot_id": str(uuid4()),
            "symbol": "EURUSD",
            "observed_at": now,
            "bid": "1.1000",
            "ask": "1.1002",
            "previous_close": "1.0990",
        },
        "account": {
            "account_id": "demo-account-without-login",
            "observed_at": now,
            "balance": "10000.00",
            "equity": "10000.00",
            "daily_realized_pnl": "0.00",
            "open_position_count": 0,
            "currency": "USD",
        },
    }


def _result(intent: dict[str, object], *, status: str, reconciliation: str) -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    return {
        "schema_version": "1.0",
        "execution_id": intent["execution_id"],
        "intent_id": intent["intent_id"],
        "status": status,
        "broker_retcode": 10009,
        "broker_retcode_description": "request completed",
        "broker_order_id": _MAX_MQL5_ULONG,
        "broker_deal_id": _MAX_MQL5_ULONG - 1,
        "requested_volume": intent["volume"],
        "filled_volume": intent["volume"],
        "requested_price": intent["requested_price"],
        "executed_price": "1.1003",
        "stop_loss": intent["stop_loss"],
        "take_profit": intent["take_profit"],
        "submitted_at": now,
        "executed_at": now,
        "reported_at": now,
        "symbol": intent["symbol"],
        "side": intent["side"],
        "reconciliation_status": reconciliation,
        "reason": "synthetic broker result",
    }


async def test_demo_decision_outboxes_and_authenticated_ea_reconciles(tmp_path: Path) -> None:
    app = create_app(settings=_settings(tmp_path / "demo.sqlite3"))
    headers = {"x-fx-execution-token": _SECRET}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        decision = await client.post("/v1/decision", json=_decision_payload())
        unauthorized = await client.get("/v1/demo-execution/next")
        claimed = await client.get("/v1/demo-execution/next", headers=headers)
        intent = claimed.json()
        blocked = await client.get("/v1/demo-execution/next", headers=headers)
        filled = await client.post(
            "/v1/demo-execution/result",
            json=_result(intent, status="filled", reconciliation="pending"),
            headers=headers,
        )
        reconciled = await client.post(
            "/v1/demo-execution/reconcile",
            json=_result(intent, status="position_confirmed", reconciliation="confirmed"),
            headers=headers,
        )
        status_response = await client.get("/v1/demo-execution/status", headers=headers)
        empty = await client.get("/v1/demo-execution/next", headers=headers)

    assert decision.status_code == 200
    assert decision.json()["status"] == "demo_queued"
    assert unauthorized.status_code == 401
    assert claimed.status_code == 200
    assert intent["order_type"] == "market"
    assert intent["volume"] == "0.01"
    assert intent["stop_loss"] is not None
    assert intent["take_profit"] is not None
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["reason"] == "reconciliation_required"
    assert filled.status_code == 200
    assert reconciled.status_code == 200
    assert status_response.json()["counts"] == {"position_confirmed": 1}
    assert status_response.json()["live_mode"] == "forbidden"
    assert empty.status_code == 204


async def test_malformed_unknown_or_conflicting_result_fails_closed(tmp_path: Path) -> None:
    app = create_app(settings=_settings(tmp_path / "demo.sqlite3"))
    headers = {"x-fx-execution-token": _SECRET}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/decision", json=_decision_payload())
        intent = (await client.get("/v1/demo-execution/next", headers=headers)).json()
        unknown_status = _result(intent, status="broker_says_ok", reconciliation="confirmed")
        malformed = await client.post(
            "/v1/demo-execution/result", json=unknown_status, headers=headers
        )
        impossible_confirmation = _result(
            intent,
            status="position_confirmed",
            reconciliation="confirmed",
        )
        impossible_confirmation["filled_volume"] = "0"
        impossible = await client.post(
            "/v1/demo-execution/result",
            json=impossible_confirmation,
            headers=headers,
        )
        conflict_payload = _result(intent, status="rejected", reconciliation="failed")
        conflict_payload["filled_volume"] = "0"
        conflict_payload["intent_id"] = str(uuid4())
        conflict = await client.post(
            "/v1/demo-execution/result", json=conflict_payload, headers=headers
        )

    assert malformed.status_code == 422
    assert impossible.status_code == 422
    assert conflict.status_code == 409
