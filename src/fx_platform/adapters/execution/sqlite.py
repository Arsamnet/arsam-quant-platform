"""Atomic DEMO-only SQLite execution outbox and reconciliation journal."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from fx_platform.application.ports import Clock
from fx_platform.domain.common import TradeSide, TradingMode
from fx_platform.domain.execution import (
    ExecutionIntent,
    ExecutionResult,
    ExecutionStatus,
    OrderType,
    ReconciliationStatus,
)

_HARD_DEMO_VOLUME_CAP = Decimal("0.01")


class ReconciliationRequiredError(RuntimeError):
    """Claimed work must be reconciled and must never be blindly redelivered."""

    def __init__(self, execution_ids: tuple[UUID, ...]) -> None:
        super().__init__("claimed demo executions require reconciliation")
        self.execution_ids = execution_ids


class ExecutionStoreConflictError(RuntimeError):
    """A replay identity or invalid state transition was detected."""


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def intent_to_wire(intent: ExecutionIntent) -> dict[str, object]:
    """Return the strict decimal-string payload polled by the MQL5 guard."""
    return {
        "schema_version": intent.schema_version,
        "execution_id": str(intent.execution_id),
        "intent_id": str(intent.intent_id),
        "request_id": str(intent.request_id),
        "node_id": intent.node_id,
        "created_at": _utc_text(intent.created_at),
        "expires_at": _utc_text(intent.expires_at),
        "symbol": intent.symbol,
        "side": intent.side.value,
        "order_type": intent.order_type.value,
        "volume": str(intent.volume),
        "requested_price": str(intent.requested_price),
        "stop_loss": str(intent.stop_loss),
        "take_profit": None if intent.take_profit is None else str(intent.take_profit),
        "maximum_spread": str(intent.maximum_spread),
        "risk_fingerprint": intent.risk_fingerprint,
        "request_fingerprint": intent.request_fingerprint,
        "nonce": intent.nonce,
        "strategy_name": intent.strategy_name,
        "strategy_version": intent.strategy_version,
        "risk_decision_id": str(intent.risk_decision_id),
        "signal_id": str(intent.signal_id),
    }


def _intent_from_wire(payload: dict[str, Any]) -> ExecutionIntent:
    return ExecutionIntent(
        schema_version=payload["schema_version"],
        execution_id=UUID(payload["execution_id"]),
        intent_id=UUID(payload["intent_id"]),
        request_id=UUID(payload["request_id"]),
        node_id=payload["node_id"],
        created_at=datetime.fromisoformat(payload["created_at"]),
        expires_at=datetime.fromisoformat(payload["expires_at"]),
        symbol=payload["symbol"],
        side=TradeSide(payload["side"]),
        order_type=OrderType(payload["order_type"]),
        volume=Decimal(payload["volume"]),
        entry_price=Decimal(payload["requested_price"]),
        stop_loss=Decimal(payload["stop_loss"]),
        take_profit=None if payload["take_profit"] is None else Decimal(payload["take_profit"]),
        maximum_spread=Decimal(payload["maximum_spread"]),
        risk_fingerprint=payload["risk_fingerprint"],
        request_fingerprint=payload["request_fingerprint"],
        nonce=payload["nonce"],
        strategy_name=payload["strategy_name"],
        strategy_version=payload["strategy_version"],
        risk_decision_id=UUID(payload["risk_decision_id"]),
        signal_id=UUID(payload["signal_id"]),
        trading_mode=TradingMode.DEMO,
    )


def result_to_wire(result: ExecutionResult) -> dict[str, object]:
    """Serialize a result without credentials or account identity."""
    payload = asdict(result)
    payload["execution_id"] = str(result.execution_id)
    payload["intent_id"] = None if result.intent_id is None else str(result.intent_id)
    payload["status"] = result.status.value
    payload["reconciliation_status"] = result.reconciliation_status.value
    payload["side"] = None if result.side is None else result.side.value
    for name in ("completed_at", "submitted_at", "executed_at", "reported_at"):
        value = getattr(result, name)
        payload[name] = None if value is None else _utc_text(value)
    for name in (
        "requested_volume",
        "filled_volume",
        "requested_price",
        "executed_price",
        "stop_loss",
        "take_profit",
    ):
        value = getattr(result, name)
        payload[name] = None if value is None else str(value)
    return payload


class SqliteDemoExecutionStore:
    """Durable single-node outbox; claimed entries require explicit reconciliation."""

    def __init__(self, path: Path, clock: Clock) -> None:
        if str(path) == ":memory:":
            raise ValueError("demo execution outbox must be durable")
        self._path = path
        self._clock = clock
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS demo_execution_outbox (
                    execution_id TEXT PRIMARY KEY,
                    intent_id TEXT NOT NULL UNIQUE,
                    request_id TEXT NOT NULL UNIQUE,
                    nonce TEXT NOT NULL UNIQUE,
                    request_fingerprint TEXT NOT NULL UNIQUE,
                    node_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    intent_json TEXT NOT NULL,
                    result_json TEXT,
                    claimed_at TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def execute(self, intent: ExecutionIntent) -> ExecutionResult:
        """Atomically enqueue one fresh DEMO intent or suppress every replay key."""
        now = self._clock.now()
        if intent.trading_mode is not TradingMode.DEMO:
            return ExecutionResult(
                execution_id=intent.execution_id,
                intent_id=intent.intent_id,
                completed_at=now,
                status=ExecutionStatus.REJECTED,
                message="demo outbox rejects non-demo intent",
            )
        if intent.volume > _HARD_DEMO_VOLUME_CAP:
            return ExecutionResult(
                execution_id=intent.execution_id,
                intent_id=intent.intent_id,
                completed_at=now,
                status=ExecutionStatus.REJECTED,
                message="demo volume exceeds hard 0.01 lot cap",
            )
        if now >= intent.expires_at:
            return ExecutionResult(
                execution_id=intent.execution_id,
                intent_id=intent.intent_id,
                completed_at=now,
                status=ExecutionStatus.REJECTED,
                message="demo execution intent expired before enqueue",
            )
        payload = json.dumps(intent_to_wire(intent), separators=(",", ":"), sort_keys=True)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO demo_execution_outbox (
                        execution_id, intent_id, request_id, nonce, request_fingerprint,
                        node_id, created_at, expires_at, status, intent_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(intent.execution_id),
                        str(intent.intent_id),
                        str(intent.request_id),
                        intent.nonce,
                        intent.request_fingerprint,
                        intent.node_id,
                        _utc_text(intent.created_at),
                        _utc_text(intent.expires_at),
                        ExecutionStatus.PENDING.value,
                        payload,
                        _utc_text(now),
                    ),
                )
                connection.commit()
        except sqlite3.IntegrityError:
            return ExecutionResult(
                execution_id=intent.execution_id,
                intent_id=intent.intent_id,
                completed_at=now,
                status=ExecutionStatus.DUPLICATE,
                message="duplicate demo execution identity suppressed",
            )
        return ExecutionResult(
            execution_id=intent.execution_id,
            intent_id=intent.intent_id,
            completed_at=now,
            status=ExecutionStatus.PENDING,
            message="risk-approved demo intent durably queued",
            requested_volume=intent.volume,
            requested_price=intent.requested_price,
            stop_loss=intent.stop_loss,
            take_profit=intent.take_profit,
            symbol=intent.symbol,
            side=intent.side,
            reconciliation_status=ReconciliationStatus.PENDING,
        )

    def claim_next(self, node_id: str) -> ExecutionIntent | None:
        """Claim one fresh item; unresolved claims block every subsequent delivery."""
        now = self._clock.now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            unresolved = connection.execute(
                "SELECT execution_id FROM demo_execution_outbox "
                "WHERE node_id = ? AND status IN (?, ?, ?, ?, ?, ?) ORDER BY created_at",
                (
                    node_id,
                    ExecutionStatus.CLAIMED.value,
                    ExecutionStatus.SUBMITTED.value,
                    ExecutionStatus.FILLED.value,
                    ExecutionStatus.PARTIALLY_FILLED.value,
                    ExecutionStatus.UNKNOWN.value,
                    ExecutionStatus.RECONCILIATION_FAILED.value,
                ),
            ).fetchall()
            if unresolved:
                connection.rollback()
                raise ReconciliationRequiredError(
                    tuple(UUID(row["execution_id"]) for row in unresolved)
                )
            rows = connection.execute(
                "SELECT execution_id, expires_at, intent_json FROM demo_execution_outbox "
                "WHERE node_id = ? AND status = ? ORDER BY created_at",
                (node_id, ExecutionStatus.PENDING.value),
            ).fetchall()
            selected: sqlite3.Row | None = None
            for row in rows:
                expiry = datetime.fromisoformat(row["expires_at"])
                if now >= expiry:
                    connection.execute(
                        "UPDATE demo_execution_outbox SET status = ?, updated_at = ? "
                        "WHERE execution_id = ?",
                        (ExecutionStatus.REJECTED.value, _utc_text(now), row["execution_id"]),
                    )
                else:
                    selected = row
                    break
            if selected is None:
                connection.commit()
                return None
            connection.execute(
                "UPDATE demo_execution_outbox SET status = ?, claimed_at = ?, updated_at = ? "
                "WHERE execution_id = ? AND status = ?",
                (
                    ExecutionStatus.CLAIMED.value,
                    _utc_text(now),
                    _utc_text(now),
                    selected["execution_id"],
                    ExecutionStatus.PENDING.value,
                ),
            )
            connection.commit()
        return _intent_from_wire(json.loads(selected["intent_json"]))

    def record_result(self, result: ExecutionResult) -> None:
        """Record a reviewed transition; unknown and failed reconciliation stay failures."""
        allowed = {
            ExecutionStatus.SUBMITTED,
            ExecutionStatus.REJECTED,
            ExecutionStatus.FILLED,
            ExecutionStatus.PARTIALLY_FILLED,
            ExecutionStatus.POSITION_CONFIRMED,
            ExecutionStatus.RECONCILIATION_FAILED,
            ExecutionStatus.UNKNOWN,
        }
        if result.status not in allowed or result.intent_id is None:
            raise ExecutionStoreConflictError("malformed or unsupported broker result status")
        payload = json.dumps(result_to_wire(result), separators=(",", ":"), sort_keys=True)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT intent_id, status, result_json, intent_json FROM demo_execution_outbox "
                "WHERE execution_id = ?",
                (str(result.execution_id),),
            ).fetchone()
            if row is None or row["intent_id"] != str(result.intent_id):
                connection.rollback()
                raise ExecutionStoreConflictError("unknown execution or intent identity")
            intent = _intent_from_wire(json.loads(row["intent_json"]))
            expected_fields = (
                (result.requested_volume, intent.volume),
                (result.requested_price, intent.requested_price),
                (result.stop_loss, intent.stop_loss),
                (result.take_profit, intent.take_profit),
                (result.symbol, intent.symbol),
                (result.side, intent.side),
            )
            if any(actual != expected for actual, expected in expected_fields):
                connection.rollback()
                raise ExecutionStoreConflictError("broker result does not match claimed intent")
            if result.filled_volume is not None and result.filled_volume > intent.volume:
                connection.rollback()
                raise ExecutionStoreConflictError("filled volume exceeds requested volume")
            previous = ExecutionStatus(row["status"])
            if previous is result.status:
                connection.rollback()
                return
            if row["result_json"] == payload:
                connection.rollback()
                return
            transitions = {
                ExecutionStatus.CLAIMED: allowed,
                ExecutionStatus.SUBMITTED: allowed - {ExecutionStatus.SUBMITTED},
                ExecutionStatus.FILLED: {
                    ExecutionStatus.POSITION_CONFIRMED,
                    ExecutionStatus.RECONCILIATION_FAILED,
                    ExecutionStatus.UNKNOWN,
                },
                ExecutionStatus.PARTIALLY_FILLED: {
                    ExecutionStatus.POSITION_CONFIRMED,
                    ExecutionStatus.RECONCILIATION_FAILED,
                    ExecutionStatus.UNKNOWN,
                },
            }
            if result.status not in transitions.get(previous, set()):
                connection.rollback()
                raise ExecutionStoreConflictError("invalid or conflicting execution transition")
            connection.execute(
                "UPDATE demo_execution_outbox SET status = ?, result_json = ?, updated_at = ? "
                "WHERE execution_id = ?",
                (
                    result.status.value,
                    payload,
                    _utc_text(self._clock.now()),
                    str(result.execution_id),
                ),
            )
            connection.commit()

    def status_counts(self) -> dict[str, int]:
        """Return non-sensitive state counts used by local status and startup checks."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM demo_execution_outbox GROUP BY status"
            ).fetchall()
        return {row["status"]: row["count"] for row in rows}

    def get_status(self, execution_id: UUID) -> ExecutionStatus | None:
        """Read one durable execution state for tests and operator diagnostics."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM demo_execution_outbox WHERE execution_id = ?",
                (str(execution_id),),
            ).fetchone()
        return None if row is None else ExecutionStatus(row["status"])
