"""Meaningful external boundaries used by application orchestration."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from fx_platform.application.models import DecisionAuditRecord
from fx_platform.domain.advisory import AiAssessment
from fx_platform.domain.economic import EconomicEvent
from fx_platform.domain.execution import ExecutionIntent, ExecutionResult
from fx_platform.domain.market import MarketSnapshot
from fx_platform.domain.strategy import SignalCandidate


class Clock(Protocol):
    """UTC clock boundary for deterministic time-sensitive testing."""

    def now(self) -> datetime:
        """Return the current aware UTC time."""
        ...


class AiAdvisor(Protocol):
    """Constrained advisory boundary with no execution capability."""

    def assess(
        self,
        *,
        assessment_id: UUID,
        evaluated_at: datetime,
        market: MarketSnapshot,
        signal: SignalCandidate,
    ) -> AiAssessment:
        """Return a validated assessment or an explicit unavailable/invalid state."""
        ...


class EconomicCalendarSnapshot(Protocol):
    """Read-only normalized calendar result."""

    @property
    def available(self) -> bool:
        """Whether the configured provider returned authoritative data."""
        ...

    @property
    def events(self) -> tuple[EconomicEvent, ...]:
        """Point-in-time events relevant to the query."""
        ...


class EconomicCalendarProvider(Protocol):
    """Economic calendar boundary; raw external text never enters domain instructions."""

    def events_for(
        self,
        *,
        symbol: str,
        window_start: datetime,
        window_end: datetime,
    ) -> EconomicCalendarSnapshot:
        """Return normalized scheduled events for a symbol and UTC window."""
        ...


class ExecutionAdapter(Protocol):
    """Idempotent execution boundary; bootstrap implementations remain paper-only."""

    def execute(self, intent: ExecutionIntent) -> ExecutionResult:
        """Execute or identify a duplicate paper intent."""
        ...


class AuditRepository(Protocol):
    """Persistence boundary checked before any execution attempt."""

    def get(self, decision_id: UUID) -> DecisionAuditRecord | None:
        """Return the latest record for a decision, proving repository availability."""
        ...

    def get_by_nonce(self, nonce: str) -> DecisionAuditRecord | None:
        """Return an existing nonce record to prevent replay."""
        ...

    def save(self, record: DecisionAuditRecord) -> None:
        """Durably upsert the latest workflow state."""
        ...
