"""SQLAlchemy repository integration without requiring a PostgreSQL service."""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fx_platform.adapters.persistence import AuditConflictError, Base, SqlAlchemyAuditRepository
from fx_platform.adapters.persistence.sqlalchemy import UtcDateTime
from fx_platform.application.models import AuditStage, DecisionAuditRecord
from tests.helpers import MARKET_ID, NOW, REQUEST_ID


def _record(
    *,
    decision_id=REQUEST_ID,
    nonce: str = "sql_nonce_1234567890",
    stage: AuditStage = AuditStage.REJECTED,
) -> DecisionAuditRecord:
    return DecisionAuditRecord(
        decision_id=decision_id,
        nonce=nonce,
        occurred_at=NOW,
        stage=stage,
        node_id="paper-node",
        market_snapshot_id=MARKET_ID,
        symbol="EURUSD",
        strategy_name="fixture",
        strategy_version="1.0.0",
        signal_id=None,
        ai_status="disabled",
        risk_decision_id=None,
        risk_approved=False,
        risk_reasons=("fixture_rejection",),
        execution_id=None,
        execution_status=None,
    )


@pytest.fixture
def repository() -> SqlAlchemyAuditRepository:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield SqlAlchemyAuditRepository(session)
    engine.dispose()


def test_repository_round_trips_aware_utc_audit_and_updates_stage(
    repository: SqlAlchemyAuditRepository,
) -> None:
    initial = _record()
    repository.save(initial)

    assert repository.get(REQUEST_ID) == initial
    assert repository.get_by_nonce(initial.nonce) == initial

    completed = _record(stage=AuditStage.COMPLETED)
    repository.save(completed)

    assert repository.get(REQUEST_ID) == completed
    assert repository.get(uuid4()) is None
    assert repository.get_by_nonce("unknown") is None


def test_repository_translates_unique_nonce_conflict(
    repository: SqlAlchemyAuditRepository,
) -> None:
    repository.save(_record())

    with pytest.raises(AuditConflictError, match="nonce"):
        repository.save(_record(decision_id=uuid4()))


def test_utc_database_type_rejects_naive_bind_and_restores_sqlite_utc() -> None:
    data_type = UtcDateTime()

    with pytest.raises(ValueError, match="UTC"):
        data_type.process_bind_param(NOW.replace(tzinfo=None), None)

    restored = data_type.process_result_value(NOW.replace(tzinfo=None), None)

    assert restored == NOW
    assert data_type.process_bind_param(None, None) is None
    assert data_type.process_result_value(None, None) is None
