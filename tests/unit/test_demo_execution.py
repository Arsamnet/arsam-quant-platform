"""Durable demo outbox, restart, transition, and risk-barrier tests."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from fx_platform.adapters.execution import (
    ExecutionStoreConflictError,
    ReconciliationRequiredError,
    SqliteDemoExecutionStore,
)
from fx_platform.domain.common import TradeSide, TradingMode
from fx_platform.domain.execution import (
    ExecutionIntent,
    ExecutionResult,
    ExecutionStatus,
    OrderType,
    ReconciliationStatus,
)
from fx_platform.domain.risk import RiskEngine, RiskLimits, RiskRejection
from tests.helpers import (
    NOW,
    FixedClock,
    make_account,
    make_assessment,
    make_market,
    make_signal,
    make_specification,
)


def _intent(**changes: object) -> ExecutionIntent:
    values: dict[str, object] = {
        "schema_version": "1.0",
        "execution_id": uuid4(),
        "intent_id": uuid4(),
        "request_id": uuid4(),
        "signal_id": uuid4(),
        "risk_decision_id": uuid4(),
        "created_at": NOW,
        "expires_at": NOW + timedelta(seconds=10),
        "node_id": "local-demo-node",
        "symbol": "EURUSD",
        "side": TradeSide.BUY,
        "order_type": OrderType.MARKET,
        "volume": Decimal("0.01"),
        "entry_price": Decimal("1.1002"),
        "stop_loss": Decimal("1.0992"),
        "take_profit": Decimal("1.1022"),
        "maximum_spread": Decimal("0.00050"),
        "risk_fingerprint": "a" * 64,
        "request_fingerprint": "b" * 64,
        "nonce": f"nonce_{uuid4().hex}",
        "strategy_name": "test_strategy",
        "strategy_version": "1.0.0",
        "trading_mode": TradingMode.DEMO,
    }
    values.update(changes)
    return ExecutionIntent(**values)


def _store(path: Path, clock: FixedClock | None = None) -> SqliteDemoExecutionStore:
    return SqliteDemoExecutionStore(path, clock or FixedClock())


def _result(intent: ExecutionIntent, **changes: object) -> ExecutionResult:
    values: dict[str, object] = {
        "execution_id": intent.execution_id,
        "intent_id": intent.intent_id,
        "completed_at": NOW,
        "reported_at": NOW,
        "status": ExecutionStatus.REJECTED,
        "message": "broker rejected safely",
        "broker_order_id": None,
        "broker_deal_id": None,
        "requested_volume": intent.volume,
        "filled_volume": Decimal(0),
        "requested_price": intent.requested_price,
        "stop_loss": intent.stop_loss,
        "take_profit": intent.take_profit,
        "symbol": intent.symbol,
        "side": intent.side,
        "reconciliation_status": ReconciliationStatus.FAILED,
    }
    values.update(changes)
    return ExecutionResult(**values)


def test_demo_outbox_is_durable_and_claimed_work_is_not_redelivered(tmp_path: Path) -> None:
    path = tmp_path / "demo.sqlite3"
    intent = _intent()
    first = _store(path)

    assert first.execute(intent).status is ExecutionStatus.PENDING
    assert first.claim_next(intent.node_id) == intent

    restarted = _store(path)
    with pytest.raises(ReconciliationRequiredError) as captured:
        restarted.claim_next(intent.node_id)

    assert captured.value.execution_ids == (intent.execution_id,)
    assert restarted.get_status(intent.execution_id) is ExecutionStatus.CLAIMED


@pytest.mark.parametrize(
    "change",
    [
        {"execution_id": uuid4()},
        {"intent_id": uuid4()},
        {"request_id": uuid4()},
        {"nonce": "different_nonce_123456", "request_fingerprint": "c" * 64},
    ],
)
def test_every_replay_identity_suppresses_a_second_outbox_entry(
    tmp_path: Path, change: dict[str, object]
) -> None:
    store = _store(tmp_path / "demo.sqlite3")
    intent = _intent()
    assert store.execute(intent).status is ExecutionStatus.PENDING

    replay_values = {
        "execution_id": intent.execution_id,
        "intent_id": intent.intent_id,
        "request_id": intent.request_id,
        "nonce": intent.nonce,
        "request_fingerprint": intent.request_fingerprint,
    }
    replay_values.update(change)
    replay = replace(intent, **replay_values)

    assert store.execute(replay).status is ExecutionStatus.DUPLICATE
    assert store.status_counts() == {ExecutionStatus.PENDING.value: 1}


def test_hard_volume_cap_and_expiry_reject_before_persistence(tmp_path: Path) -> None:
    store = _store(tmp_path / "demo.sqlite3")

    oversized = store.execute(_intent(volume=Decimal("0.02")))
    expired = _store(tmp_path / "expired.sqlite3", FixedClock(NOW + timedelta(seconds=10))).execute(
        _intent()
    )

    assert oversized.status is ExecutionStatus.REJECTED
    assert expired.status is ExecutionStatus.REJECTED
    assert store.status_counts() == {}


def test_result_state_machine_fails_closed_and_confirms_only_reconciled_position(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / "demo.sqlite3")
    intent = _intent()
    store.execute(intent)
    store.claim_next(intent.node_id)

    filled = _result(
        intent,
        status=ExecutionStatus.FILLED,
        message="deal reported; reconciliation pending",
        broker_order_id=123456,
        broker_deal_id=654321,
        filled_volume=intent.volume,
        executed_price=Decimal("1.1003"),
        reconciliation_status=ReconciliationStatus.PENDING,
    )
    store.record_result(filled)
    assert store.get_status(intent.execution_id) is ExecutionStatus.FILLED

    confirmed = _result(
        intent,
        status=ExecutionStatus.POSITION_CONFIRMED,
        message="matching position confirmed",
        broker_order_id=123456,
        broker_deal_id=654321,
        filled_volume=intent.volume,
        executed_price=Decimal("1.1003"),
        reconciliation_status=ReconciliationStatus.CONFIRMED,
    )
    store.record_result(confirmed)
    assert store.get_status(intent.execution_id) is ExecutionStatus.POSITION_CONFIRMED

    with pytest.raises(ExecutionStoreConflictError):
        store.record_result(_result(intent, status=ExecutionStatus.UNKNOWN))


def test_unknown_reconciliation_blocks_every_later_claim(tmp_path: Path) -> None:
    path = tmp_path / "demo.sqlite3"
    store = _store(path)
    intent = _intent()
    store.execute(intent)
    store.claim_next(intent.node_id)
    store.record_result(
        _result(
            intent,
            status=ExecutionStatus.UNKNOWN,
            message="submission outcome uncertain",
            reconciliation_status=ReconciliationStatus.UNKNOWN,
        )
    )

    with pytest.raises(ReconciliationRequiredError):
        _store(path).claim_next(intent.node_id)


def test_repeated_equivalent_terminal_result_is_idempotent(tmp_path: Path) -> None:
    store = _store(tmp_path / "demo.sqlite3")
    intent = _intent()
    store.execute(intent)
    store.claim_next(intent.node_id)
    first = _result(intent)

    store.record_result(first)
    store.record_result(
        replace(first, message="same rejection reported after lost acknowledgement")
    )

    assert store.get_status(intent.execution_id) is ExecutionStatus.REJECTED


def test_result_must_match_claimed_financial_and_symbol_facts(tmp_path: Path) -> None:
    store = _store(tmp_path / "demo.sqlite3")
    intent = _intent()
    store.execute(intent)
    store.claim_next(intent.node_id)

    with pytest.raises(ExecutionStoreConflictError, match="does not match"):
        store.record_result(_result(intent, requested_volume=Decimal("0.02")))


@pytest.mark.parametrize(
    "changes",
    [
        {
            "status": ExecutionStatus.POSITION_CONFIRMED,
            "reconciliation_status": ReconciliationStatus.CONFIRMED,
            "filled_volume": Decimal(0),
            "executed_price": Decimal("1.1003"),
            "broker_order_id": 123456,
        },
        {
            "status": ExecutionStatus.FILLED,
            "reconciliation_status": ReconciliationStatus.PENDING,
            "filled_volume": Decimal("0.01"),
            "executed_price": None,
            "broker_deal_id": 654321,
        },
        {
            "status": ExecutionStatus.PARTIALLY_FILLED,
            "reconciliation_status": ReconciliationStatus.PENDING,
            "filled_volume": Decimal("0.005"),
            "executed_price": Decimal("1.1003"),
        },
        {
            "status": ExecutionStatus.SUBMITTED,
            "reconciliation_status": ReconciliationStatus.PENDING,
        },
        {"filled_volume": Decimal("0.001")},
    ],
)
def test_broker_status_cannot_claim_impossible_execution_facts(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        _result(_intent(), **changes)


def test_demo_risk_requires_tp_and_keeps_volume_spread_position_and_grid_limits() -> None:
    engine = RiskEngine(
        RiskLimits(
            allowed_symbols=frozenset({"EURUSD"}),
            max_volume=Decimal("0.01"),
            max_open_positions=1,
            require_take_profit=True,
        )
    )

    def evaluate(**signal_changes: object):
        wide = bool(signal_changes.pop("wide", False))
        positions = int(signal_changes.pop("positions", 0))
        signal = make_signal(**signal_changes)
        return engine.evaluate(
            risk_decision_id=uuid4(),
            evaluated_at=NOW,
            trading_mode=TradingMode.DEMO,
            market=make_market(ask=Decimal("1.1010") if wide else Decimal("1.1002")),
            account=make_account(open_position_count=positions),
            signal=signal,
            ai_assessment=make_assessment(signal_id=signal.signal_id),
            economic_events=(),
            calendar_available=False,
            symbol_specification=make_specification(),
        )

    missing_tp = evaluate(take_profit=None)
    oversized = evaluate(volume=Decimal("0.02"))
    position_limited = evaluate(positions=1)
    spread_limited = evaluate(wide=True)

    assert RiskRejection.MISSING_TAKE_PROFIT in missing_tp.reasons
    assert RiskRejection.VOLUME_LIMIT_EXCEEDED in oversized.reasons
    assert RiskRejection.POSITION_LIMIT_EXCEEDED in position_limited.reasons
    assert RiskRejection.SPREAD_TOO_WIDE in spread_limited.reasons


def test_broker_price_roundtrip_residue_does_not_conflict(tmp_path: Path) -> None:
    store = _store(tmp_path / "demo.sqlite3")
    intent = _intent(
        entry_price=Decimal("1.1472800000000001"),
        stop_loss=Decimal("1.1482800000000001"),
        take_profit=Decimal("1.1452800000000001"),
    )

    assert store.execute(intent).status is ExecutionStatus.PENDING
    assert store.claim_next(intent.node_id) == intent

    store.record_result(
        _result(
            intent,
            status=ExecutionStatus.POSITION_CONFIRMED,
            requested_price=Decimal("1.14728"),
            stop_loss=Decimal("1.14828"),
            take_profit=Decimal("1.14528"),
            filled_volume=Decimal("0.01"),
            executed_price=Decimal("1.14727"),
            broker_order_id=123456,
            broker_deal_id=654321,
            reconciliation_status=ReconciliationStatus.CONFIRMED,
            message="broker-confirmed position",
        )
    )

    assert store.get_status(intent.execution_id) is ExecutionStatus.POSITION_CONFIRMED


def test_real_broker_price_difference_still_conflicts(tmp_path: Path) -> None:
    store = _store(tmp_path / "demo.sqlite3")
    intent = _intent(
        entry_price=Decimal("1.1472800000000001"),
        stop_loss=Decimal("1.1482800000000001"),
        take_profit=Decimal("1.1452800000000001"),
    )

    assert store.execute(intent).status is ExecutionStatus.PENDING
    assert store.claim_next(intent.node_id) == intent

    with pytest.raises(
        ExecutionStoreConflictError,
        match="does not match claimed intent",
    ):
        store.record_result(
            _result(
                intent,
                requested_price=Decimal("1.14729"),
                stop_loss=Decimal("1.14828"),
                take_profit=Decimal("1.14528"),
            )
        )
