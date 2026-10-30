"""Fail-closed autonomous DEMO orchestration and snapshot adapter tests."""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from fx_platform.adapters.market.autonomous import FileAutonomousSnapshotSource
from fx_platform.application.autonomy import (
    AutonomousDemoSupervisor,
    AutonomousMarketObservation,
    AutonomousSnapshot,
    AutonomousSnapshotError,
)
from fx_platform.application.models import DecisionOutcome, DecisionOutcomeStatus
from fx_platform.domain.market import AccountSnapshot, MarketSnapshot
from tests.helpers import NOW, FixedClock


class _Source:
    def __init__(self, snapshot: AutonomousSnapshot) -> None:
        self.snapshot = snapshot
        self.read_count = 0

    def read(self) -> AutonomousSnapshot:
        self.read_count += 1
        return self.snapshot


class _ExecutionState:
    def __init__(self, counts: dict[str, int] | None = None) -> None:
        self.counts = counts or {}

    def status_counts(self) -> dict[str, int]:
        return self.counts


class _Service:
    def __init__(self, status: DecisionOutcomeStatus = DecisionOutcomeStatus.NO_SIGNAL) -> None:
        self.status = status
        self.commands = []

    def decide(self, command):
        self.commands.append(command)
        return DecisionOutcome(
            request_id=command.request_id,
            status=self.status,
            signal_id=None,
            risk_decision_id=None,
            execution_id=None,
            execution_status=None,
            reasons=("test",),
        )


def _observation(
    *,
    symbol: str = "EURUSD",
    base_currency: str = "EUR",
    quote_currency: str = "USD",
    bid: Decimal = Decimal("1.1000"),
    ask: Decimal = Decimal("1.1002"),
    previous_close: Decimal = Decimal("1.0990"),
) -> AutonomousMarketObservation:
    return AutonomousMarketObservation(
        market=MarketSnapshot(
            snapshot_id=UUID("10000000-0000-4000-8000-000000000001"),
            symbol=symbol,
            observed_at=NOW,
            bid=bid,
            ask=ask,
            previous_close=previous_close,
        ),
        decision_bar_time=NOW - timedelta(minutes=5),
        base_currency=base_currency,
        quote_currency=quote_currency,
    )


def _snapshot(*markets: AutonomousMarketObservation) -> AutonomousSnapshot:
    return AutonomousSnapshot(
        acquired_at=NOW,
        account=AccountSnapshot(
            account_id="fibo-demo-usd-local",
            observed_at=NOW,
            balance=Decimal(10000),
            equity=Decimal(10000),
            daily_realized_pnl=Decimal(0),
            open_position_count=0,
            currency="USD",
        ),
        markets=markets or (_observation(),),
    )


def _supervisor(
    *,
    source: _Source,
    service: _Service,
    state: _ExecutionState | None = None,
) -> AutonomousDemoSupervisor:
    return AutonomousDemoSupervisor(
        service=service,
        source=source,
        execution_state=state or _ExecutionState(),
        clock=FixedClock(),
        node_id="local-demo-node",
        allowed_symbols=frozenset({"EURUSD", "GBPUSD", "USDJPY"}),
        max_snapshot_age=timedelta(seconds=15),
    )


def test_supervisor_processes_each_symbol_bar_only_once() -> None:
    source = _Source(_snapshot())
    service = _Service()
    supervisor = _supervisor(source=source, service=service)

    first = supervisor.run_cycle()
    second = supervisor.run_cycle()

    assert len(first) == 1
    assert second == ()
    assert len(service.commands) == 1
    assert service.commands[0].nonce.startswith("auto_")


def test_supervisor_does_not_read_market_while_execution_state_is_unresolved() -> None:
    source = _Source(_snapshot())
    service = _Service()
    supervisor = _supervisor(
        source=source,
        service=service,
        state=_ExecutionState({"pending": 1}),
    )

    assert supervisor.run_cycle() == ()
    assert source.read_count == 0
    assert service.commands == []


def test_supervisor_stops_after_first_queued_demo_intent() -> None:
    eurusd = _observation()
    gbpusd = AutonomousMarketObservation(
        market=MarketSnapshot(
            snapshot_id=UUID("10000000-0000-4000-8000-000000000002"),
            symbol="GBPUSD",
            observed_at=NOW,
            bid=Decimal("1.3000"),
            ask=Decimal("1.3002"),
            previous_close=Decimal("1.2990"),
        ),
        decision_bar_time=NOW - timedelta(minutes=5),
        base_currency="GBP",
        quote_currency="USD",
    )
    source = _Source(_snapshot(eurusd, gbpusd))
    service = _Service(DecisionOutcomeStatus.DEMO_QUEUED)

    outcomes = _supervisor(source=source, service=service).run_cycle()

    assert len(outcomes) == 1
    assert len(service.commands) == 1


def test_supervisor_derives_exact_inverse_usdjpy_conversion() -> None:
    source = _Source(
        _snapshot(
            _observation(
                symbol="USDJPY",
                base_currency="USD",
                quote_currency="JPY",
                bid=Decimal("157.776"),
                ask=Decimal("157.786"),
                previous_close=Decimal("157.000"),
            )
        )
    )
    service = _Service()

    _supervisor(source=source, service=service).run_cycle()

    command = service.commands[0]
    assert len(command.inverse_conversion_derivations) == 1
    derivation = command.inverse_conversion_derivations[0]
    assert derivation.conversion_rate.source_currency == "JPY"
    assert derivation.conversion_rate.target_currency == "USD"
    assert derivation.conversion_rate.rate == Decimal(1) / Decimal("157.776")


def test_supervisor_rejects_stale_snapshot_before_decision() -> None:
    stale = AutonomousSnapshot(
        acquired_at=NOW - timedelta(seconds=16),
        account=AccountSnapshot(
            account_id="fibo-demo-usd-local",
            observed_at=NOW - timedelta(seconds=16),
            balance=Decimal(10000),
            equity=Decimal(10000),
            daily_realized_pnl=Decimal(0),
            open_position_count=0,
            currency="USD",
        ),
        markets=(_observation(),),
    )
    source = _Source(stale)
    service = _Service()

    with pytest.raises(AutonomousSnapshotError, match="stale"):
        _supervisor(source=source, service=service).run_cycle()

    assert service.commands == []


def _snapshot_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "mode": "autonomous_demo_snapshot",
        "source_type": "mql5_autonomous_probe",
        "acquired_at": NOW.isoformat(),
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
            "balance": "10000.00",
            "equity": "10000.00",
            "daily_realized_pnl": "0.00",
            "open_position_count": 0,
        },
        "symbols": [
            {
                "name": "EURUSD",
                "base_currency": "EUR",
                "quote_currency": "USD",
                "bid": "1.1000",
                "ask": "1.1002",
                "previous_close": "1.0990",
                "observed_at": NOW.isoformat(),
                "decision_bar_time": (NOW - timedelta(minutes=5)).isoformat(),
                "tick_age_seconds": 1,
                "trade_mode_code": 4,
            },
            {
                "name": "GBPUSD",
                "base_currency": "GBP",
                "quote_currency": "USD",
                "bid": "1.3000",
                "ask": "1.3002",
                "previous_close": "1.2990",
                "observed_at": NOW.isoformat(),
                "decision_bar_time": (NOW - timedelta(minutes=5)).isoformat(),
                "tick_age_seconds": 1,
                "trade_mode_code": 4,
            },
            {
                "name": "USDJPY",
                "base_currency": "USD",
                "quote_currency": "JPY",
                "bid": "157.776",
                "ask": "157.786",
                "previous_close": "157.000",
                "observed_at": NOW.isoformat(),
                "decision_bar_time": (NOW - timedelta(minutes=5)).isoformat(),
                "tick_age_seconds": 1,
                "trade_mode_code": 4,
            },
        ],
    }


def _file_source(path: Path) -> FileAutonomousSnapshotSource:
    return FileAutonomousSnapshotSource(
        path=path,
        expected_broker_company="FIBO Group, Ltd",
        expected_broker_server="FIBOGroup-MT5 Server",
        expected_account_currency="USD",
        expected_leverage=100,
        allowed_symbols=frozenset({"EURUSD", "GBPUSD", "USDJPY"}),
        account_id="fibo-demo-usd-local",
        max_tick_age_seconds=15,
    )


def test_file_source_parses_reviewed_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(_snapshot_payload()), encoding="utf-8")

    snapshot = _file_source(path).read()

    assert snapshot.account.balance == Decimal("10000.00")
    assert {item.market.symbol for item in snapshot.markets} == {
        "EURUSD",
        "GBPUSD",
        "USDJPY",
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("broker", {"company": "Wrong", "server": "FIBOGroup-MT5 Server"}, "identity"),
        ("terminal", {"connected": False}, "account"),
    ],
)
def test_file_source_rejects_identity_or_terminal_mismatch(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    payload = _snapshot_payload()
    payload[field] = value
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AutonomousSnapshotError, match=message):
        _file_source(path).read()


def test_file_source_rejects_stale_tick(tmp_path: Path) -> None:
    payload = _snapshot_payload()
    symbols = payload["symbols"]
    assert isinstance(symbols, list)
    first = symbols[0]
    assert isinstance(first, dict)
    first["tick_age_seconds"] = 16
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AutonomousSnapshotError, match="stale"):
        _file_source(path).read()
