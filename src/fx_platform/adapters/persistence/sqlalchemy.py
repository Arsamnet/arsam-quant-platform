"""SQLAlchemy 2.x audit persistence targeting PostgreSQL."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, String, Uuid, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.types import TypeDecorator

from fx_platform.application.models import AuditStage, DecisionAuditRecord
from fx_platform.domain.common import require_utc


class AuditConflictError(RuntimeError):
    """A request ID or nonce violated the durable idempotency contract."""


class UtcDateTime(TypeDecorator[datetime]):
    """Store aware UTC values and restore driver-naive UTC values at the adapter boundary."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        del dialect
        if value is not None:
            require_utc(value, "database timestamp")
        return value

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        del dialect
        if value is None:
            return None
        # SQLite drops timezone metadata; the column contract guarantees stored values are UTC.
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    """Declarative metadata root imported by Alembic."""


class DecisionAuditRow(Base):
    """Latest durable stage for one idempotent decision workflow."""

    __tablename__ = "decision_audit_records"

    decision_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    node_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    market_snapshot_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    ai_status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_decision_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    risk_approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    risk_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    execution_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    execution_status: Mapped[str | None] = mapped_column(String(32), nullable=True)


class SqlAlchemyAuditRepository:
    """Transactional latest-state repository with durable nonce uniqueness."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, decision_id: UUID) -> DecisionAuditRecord | None:
        """Fetch the latest audit stage by decision ID."""
        row = self._session.get(DecisionAuditRow, decision_id)
        return None if row is None else self._to_domain(row)

    def get_by_nonce(self, nonce: str) -> DecisionAuditRecord | None:
        """Fetch by unique replay-prevention nonce."""
        row = self._session.scalar(select(DecisionAuditRow).where(DecisionAuditRow.nonce == nonce))
        return None if row is None else self._to_domain(row)

    def save(self, record: DecisionAuditRecord) -> None:
        """Insert or update the latest stage atomically within one database transaction."""
        row = self._session.get(DecisionAuditRow, record.decision_id)
        if row is None:
            row = DecisionAuditRow(decision_id=record.decision_id)
            self._session.add(row)
        self._copy_to_row(record, row)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise AuditConflictError("decision ID or nonce already exists") from error

    @staticmethod
    def _copy_to_row(record: DecisionAuditRecord, row: DecisionAuditRow) -> None:
        row.nonce = record.nonce
        row.occurred_at = record.occurred_at
        row.stage = record.stage.value
        row.node_id = record.node_id
        row.market_snapshot_id = record.market_snapshot_id
        row.symbol = record.symbol
        row.strategy_name = record.strategy_name
        row.strategy_version = record.strategy_version
        row.signal_id = record.signal_id
        row.ai_status = record.ai_status
        row.risk_decision_id = record.risk_decision_id
        row.risk_approved = record.risk_approved
        row.risk_reasons = list(record.risk_reasons)
        row.execution_id = record.execution_id
        row.execution_status = record.execution_status

    @staticmethod
    def _to_domain(row: DecisionAuditRow) -> DecisionAuditRecord:
        return DecisionAuditRecord(
            decision_id=row.decision_id,
            nonce=row.nonce,
            occurred_at=row.occurred_at,
            stage=AuditStage(row.stage),
            node_id=row.node_id,
            market_snapshot_id=row.market_snapshot_id,
            symbol=row.symbol,
            strategy_name=row.strategy_name,
            strategy_version=row.strategy_version,
            signal_id=row.signal_id,
            ai_status=row.ai_status,
            risk_decision_id=row.risk_decision_id,
            risk_approved=row.risk_approved,
            risk_reasons=tuple(row.risk_reasons),
            execution_id=row.execution_id,
            execution_status=row.execution_status,
        )
