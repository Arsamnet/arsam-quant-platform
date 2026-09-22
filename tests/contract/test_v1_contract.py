"""Versioned MQL5/Python envelope, authentication, and error contract tests."""

import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from fx_platform.api.contracts import DecisionRequest
from fx_platform.api.main import create_app
from fx_platform.config import Settings
from tests.integration.test_api import _payload
from tests.unit.test_decision_service import _service

pytestmark = pytest.mark.anyio


def test_v1_schema_requires_replay_and_trace_fields() -> None:
    schema = DecisionRequest.model_json_schema()

    assert set(schema["required"]) == {
        "schema_version",
        "request_id",
        "timestamp",
        "nonce",
        "node_id",
        "market",
        "account",
    }
    assert schema["properties"]["schema_version"]["const"] == "1.0"
    assert "conversion_rates" not in schema["required"]
    assert "inverse_conversion_quotes" not in schema["required"]


async def test_unsupported_version_and_short_nonce_are_malformed_requests() -> None:
    service, executor, _ = _service()
    app = create_app(
        settings=Settings(_env_file=None, node_id="paper-node"),
        service=service,
    )
    payload = _payload()
    payload["schema_version"] = "2.0"
    payload["nonce"] = "short"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/decision", json=payload)

    assert response.status_code == 422
    assert executor.executed_intents == ()


async def test_hmac_enabled_contract_rejects_missing_or_modified_signature() -> None:
    secret = "contract-test-secret"
    service, executor, _ = _service()
    app = create_app(
        settings=Settings(
            _env_file=None,
            node_id="paper-node",
            hmac_secret=SecretStr(secret),
        ),
        service=service,
    )
    payload = _payload()
    body = json.dumps(payload, separators=(",", ":")).encode()
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.post(
            "/v1/decision", content=body, headers={"content-type": "application/json"}
        )
        modified = await client.post(
            "/v1/decision",
            content=body + b" ",
            headers={
                "content-type": "application/json",
                "x-fx-signature": f"sha256={digest}",
            },
        )
        malformed = await client.post(
            "/v1/decision",
            content=body,
            headers={
                "content-type": "application/json",
                "x-fx-signature": "sha256=not-a-valid-digest",
            },
        )
        incorrect = await client.post(
            "/v1/decision",
            content=body,
            headers={
                "content-type": "application/json",
                "x-fx-signature": f"sha256={'0' * 64}",
            },
        )
        accepted = await client.post(
            "/v1/decision",
            content=body,
            headers={
                "content-type": "application/json",
                "x-fx-signature": f"sha256={digest}",
            },
        )

    assert missing.status_code == 401
    assert modified.status_code == 401
    assert malformed.status_code == 401
    assert incorrect.status_code == 401
    assert accepted.status_code == 200
    assert len(executor.executed_intents) == 1


async def test_replay_protection_remains_independent_when_hmac_is_enabled() -> None:
    secret = "contract-test-secret"
    service, executor, _ = _service()
    app = create_app(
        settings=Settings(
            _env_file=None,
            node_id="paper-node",
            hmac_secret=SecretStr(secret),
        ),
        service=service,
    )
    first_payload = _payload()
    replay_payload = dict(first_payload)
    replay_payload["request_id"] = str(uuid4())

    def signed_body(payload: dict[str, object]) -> tuple[bytes, dict[str, str]]:
        body = json.dumps(payload, separators=(",", ":")).encode()
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return body, {
            "content-type": "application/json",
            "x-fx-signature": f"sha256={digest}",
        }

    first_body, first_headers = signed_body(first_payload)
    replay_body, replay_headers = signed_body(replay_payload)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/v1/decision",
            content=first_body,
            headers=first_headers,
        )
        replay = await client.post(
            "/v1/decision",
            content=replay_body,
            headers=replay_headers,
        )

    assert first.json()["status"] == "paper_executed"
    assert replay.json()["status"] == "duplicate"
    assert len(executor.executed_intents) == 1


class _ExplodingService:
    def decide(self, command):
        del command
        raise RuntimeError("sensitive internal failure detail")


async def test_unexpected_exception_returns_generic_fail_closed_response() -> None:
    app = create_app(
        settings=Settings(_env_file=None, node_id="paper-node"),
        service=_ExplodingService(),
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/decision", json=_payload())

    assert response.status_code == 503
    assert response.json() == {"detail": "decision infrastructure unavailable; request rejected"}
    assert "sensitive" not in response.text


async def test_duplicate_contract_request_returns_same_trace_without_second_execution() -> None:
    service, executor, _ = _service()
    app = create_app(
        settings=Settings(_env_file=None, node_id="paper-node"),
        service=service,
    )
    payload = _payload()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = (await client.post("/v1/decision", json=payload)).json()
        duplicate = (await client.post("/v1/decision", json=payload)).json()

    assert first["status"] == "paper_executed"
    assert duplicate["status"] == "duplicate"
    assert duplicate["execution_id"] == first["execution_id"]
    assert len(executor.executed_intents) == 1


async def test_reusing_nonce_with_new_request_id_is_replay_rejection() -> None:
    service, executor, _ = _service()
    app = create_app(
        settings=Settings(_env_file=None, node_id="paper-node"),
        service=service,
    )
    first_payload = _payload()
    replay_payload = dict(first_payload)
    replay_payload["request_id"] = str(uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/v1/decision", json=first_payload)
        replay = await client.post("/v1/decision", json=replay_payload)

    assert first.json()["status"] == "paper_executed"
    assert replay.json()["status"] == "duplicate"
    assert len(executor.executed_intents) == 1
