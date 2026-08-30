"""Thread-safe audit repository for local development and deterministic tests."""

from threading import Lock
from uuid import UUID

from fx_platform.application.models import DecisionAuditRecord


class InMemoryAuditRepository:
    """Upsert latest audit stages and enforce request/nonce uniqueness in memory."""

    def __init__(self) -> None:
        self._records: dict[UUID, DecisionAuditRecord] = {}
        self._nonce_index: dict[str, UUID] = {}
        self._lock = Lock()

    def get(self, decision_id: UUID) -> DecisionAuditRecord | None:
        """Return the latest record for a decision ID."""
        with self._lock:
            return self._records.get(decision_id)

    def get_by_nonce(self, nonce: str) -> DecisionAuditRecord | None:
        """Return the latest record associated with a nonce."""
        with self._lock:
            decision_id = self._nonce_index.get(nonce)
            return None if decision_id is None else self._records[decision_id]

    def save(self, record: DecisionAuditRecord) -> None:
        """Upsert one decision while rejecting nonce reuse across different IDs."""
        with self._lock:
            nonce_owner = self._nonce_index.get(record.nonce)
            if nonce_owner is not None and nonce_owner != record.decision_id:
                raise ValueError("nonce already belongs to another decision")
            self._records[record.decision_id] = record
            self._nonce_index[record.nonce] = record.decision_id
