"""FastAPI integration tests over the complete in-memory paper workflow."""

from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from fx_platform.adapters.market import StaticSymbolSpecificationProvider
from fx_platform.api.main import create_app
from fx_platform.config import Settings
from fx_platform.domain.risk import RiskEngine, RiskLimits
from tests.helpers import NOW, make_specification
from tests.unit.test_decision_service import _service

pytestmark = pytest.mark.anyio


def _payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "request_id": str(uuid4()),
        "timestamp": NOW.isoformat(),
        "nonce": f"nonce_{uuid4().hex}",
        "node_id": "paper-node",
        "market": {
            "snapshot_id": str(uuid4()),
            "symbol": "EURUSD",
            "observed_at": NOW.isoformat(),
            "bid": "1.1000",
            "ask": "1.1002",
            "previous_close": "1.0990",
        },
        "account": {
            "account_id": "paper-account",
            "observed_at": NOW.isoformat(),
            "balance": "10000.00",
            "equity": "10000.00",
            "daily_realized_pnl": "0.00",
            "open_position_count": 0,
            "currency": "USD",
        },
    }


def _usdjpy_payload() -> dict[str, object]:
    payload = _payload()
    market = payload["market"]
    assert isinstance(market, dict)
    market.update(
        {
            "symbol": "USDJPY",
            "bid": "157.776",
            "ask": "157.786",
            "previous_close": "156.868",
        }
    )
    return payload


def _inverse_usdjpy_quote(*, observed_at: str | None = None) -> dict[str, object]:
    return {
        "source_currency": "JPY",
        "target_currency": "USD",
        "source_symbol": "USDJPY",
        "pair_base_currency": "USD",
        "pair_quote_currency": "JPY",
        "bid": "157.776",
        "ask": "157.786",
        "observed_at": observed_at or NOW.isoformat(),
    }


def _usdjpy_service():
    specification = make_specification(
        symbol="USDJPY",
        base_currency="USD",
        quote_currency="JPY",
        tick_size=Decimal("0.001"),
        tick_value=Decimal(100),
        tick_value_currency="JPY",
    )
    return _service(
        risk_engine=RiskEngine(RiskLimits(allowed_symbols=frozenset({"USDJPY"}))),
        symbol_specifications=StaticSymbolSpecificationProvider((specification,)),
    )


@asynccontextmanager
async def _client():
    service, executor, repository = _service()
    settings = Settings(_env_file=None, node_id="paper-node")
    transport = ASGITransport(app=create_app(settings=settings, service=service))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, executor, repository


async def test_health_reports_only_non_sensitive_safe_mode() -> None:
    async with _client() as (client, _, _):
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.6.0",
        "trading_mode": "paper",
        "ai_mode": "disabled",
        "node_id": "paper-node",
    }


async def test_decision_endpoint_completes_deterministic_paper_flow() -> None:
    async with _client() as (client, executor, repository):
        response = await client.post("/v1/decision", json=_payload())
        body = response.json()

    assert response.status_code == 200
    assert body["schema_version"] == "1.0"
    assert body["status"] == "paper_executed"
    assert body["execution_status"] == "paper_filled"
    assert body["execution_id"] is not None
    assert len(executor.executed_intents) == 1
    assert repository.get(uuid4()) is None


async def test_unknown_symbol_is_a_risk_rejection_and_never_executes() -> None:
    payload = _payload()
    market = payload["market"]
    assert isinstance(market, dict)
    market["symbol"] = "GBPUSD"

    async with _client() as (client, executor, _):
        response = await client.post("/v1/decision", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "risk_rejected"
    assert body["reasons"] == ["unknown_symbol"]
    assert body["signal_id"] is None
    assert body["risk_decision_id"] is None
    assert body["execution_id"] is None
    assert executor.executed_intents == ()


async def test_daily_loss_boundary_is_a_risk_rejection() -> None:
    payload = _payload()
    account = payload["account"]
    assert isinstance(account, dict)
    account["daily_realized_pnl"] = "-200.00"

    async with _client() as (client, executor, _):
        response = await client.post("/v1/decision", json=payload)

    assert "daily_loss_limit_exceeded" in response.json()["reasons"]
    assert executor.executed_intents == ()


async def test_request_validation_rejects_unsafe_shapes() -> None:
    payloads = []

    numeric = deepcopy(_payload())
    numeric_market = numeric["market"]
    assert isinstance(numeric_market, dict)
    numeric_market["bid"] = 1.1
    payloads.append(numeric)

    naive = deepcopy(_payload())
    naive["timestamp"] = NOW.replace(tzinfo=None).isoformat()
    payloads.append(naive)

    extra = deepcopy(_payload())
    extra["broker_password"] = "must-never-be-accepted"
    payloads.append(extra)

    async with _client() as (client, executor, _):
        for payload in payloads:
            response = await client.post("/v1/decision", json=payload)
            assert response.status_code == 422

        assert executor.executed_intents == ()


async def test_stale_market_data_is_rejected() -> None:
    payload = _payload()
    market = payload["market"]
    assert isinstance(market, dict)
    market["observed_at"] = (NOW - timedelta(minutes=1)).isoformat()

    async with _client() as (client, executor, _):
        response = await client.post("/v1/decision", json=payload)

    assert "market_data_stale" in response.json()["reasons"]
    assert executor.executed_intents == ()


async def test_decimal_strings_preserve_exact_values_to_execution() -> None:
    async with _client() as (client, executor, _):
        response = await client.post("/v1/decision", json=_payload())

        assert response.status_code == 200
        intent = executor.executed_intents[0]
        assert intent.entry_price == Decimal("1.1002")
        assert intent.volume == Decimal("0.01")


async def test_usdjpy_request_uses_explicit_jpy_to_usd_conversion() -> None:
    service, executor, _ = _usdjpy_service()
    payload = _usdjpy_payload()
    payload["conversion_rates"] = [
        {
            "source_currency": "JPY",
            "target_currency": "USD",
            "rate": "0.0067",
            "observed_at": NOW.isoformat(),
        }
    ]
    app = create_app(
        settings=Settings(_env_file=None, node_id="paper-node"),
        service=service,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/decision", json=payload)

    assert response.json()["status"] == "paper_executed"
    assert len(executor.executed_intents) == 1


async def test_usdjpy_without_conversion_remains_fail_closed() -> None:
    service, executor, _ = _usdjpy_service()
    app = create_app(
        settings=Settings(_env_file=None, node_id="paper-node"),
        service=service,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/decision", json=_usdjpy_payload())

    assert response.status_code == 200
    assert response.json()["status"] == "risk_rejected"
    assert response.json()["reasons"] == ["conversion_rate_unavailable"]
    assert response.json()["execution_id"] is None
    assert executor.executed_intents == ()


async def test_usdjpy_request_derives_jpy_to_usd_from_fresh_exact_inverse_quote() -> None:
    service, executor, _ = _usdjpy_service()
    payload = _usdjpy_payload()
    payload["inverse_conversion_quotes"] = [_inverse_usdjpy_quote()]
    app = create_app(
        settings=Settings(_env_file=None, node_id="paper-node"),
        service=service,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/decision", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "paper_executed"
    assert len(executor.executed_intents) == 1


@pytest.mark.parametrize(
    ("observed_at", "reason"),
    [
        ((NOW - timedelta(seconds=31)).isoformat(), "conversion_rate_stale"),
        ((NOW + timedelta(seconds=3)).isoformat(), "conversion_rate_in_future"),
    ],
)
async def test_stale_or_future_inverse_quote_rejects_without_execution(
    observed_at: str,
    reason: str,
) -> None:
    service, executor, _ = _usdjpy_service()
    payload = _usdjpy_payload()
    payload["inverse_conversion_quotes"] = [_inverse_usdjpy_quote(observed_at=observed_at)]
    app = create_app(
        settings=Settings(_env_file=None, node_id="paper-node"),
        service=service,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/decision", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "risk_rejected"
    assert reason in response.json()["reasons"]
    assert response.json()["execution_id"] is None
    assert executor.executed_intents == ()


async def test_direct_and_derived_applicable_rates_reject_as_ambiguous() -> None:
    service, executor, _ = _usdjpy_service()
    payload = _usdjpy_payload()
    payload["conversion_rates"] = [
        {
            "source_currency": "JPY",
            "target_currency": "USD",
            "rate": "0.0067",
            "observed_at": NOW.isoformat(),
        }
    ]
    payload["inverse_conversion_quotes"] = [_inverse_usdjpy_quote()]
    app = create_app(
        settings=Settings(_env_file=None, node_id="paper-node"),
        service=service,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/decision", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "risk_rejected"
    assert "conversion_rate_ambiguous" in response.json()["reasons"]
    assert response.json()["execution_id"] is None
    assert executor.executed_intents == ()


@pytest.mark.parametrize(
    "changes",
    [
        {"source_symbol": "EURJPY", "pair_base_currency": "EUR"},
        {"source_currency": "EUR"},
        {"source_currency": "USD", "target_currency": "USD"},
        {"bid": "0"},
        {"bid": "-1"},
        {"ask": "0"},
        {"ask": "-1"},
        {"bid": "157.787"},
        {"source_symbol": "EURJPY"},
        {"source_currency": "jpy"},
    ],
)
async def test_invalid_or_non_inverse_quote_is_schema_rejected(
    changes: dict[str, object],
) -> None:
    service, executor, _ = _usdjpy_service()
    payload = _usdjpy_payload()
    quote = _inverse_usdjpy_quote()
    quote.update(changes)
    payload["inverse_conversion_quotes"] = [quote]
    app = create_app(
        settings=Settings(_env_file=None, node_id="paper-node"),
        service=service,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/decision", json=payload)

    assert response.status_code == 422
    assert executor.executed_intents == ()
