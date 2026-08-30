"""Framework-independent application commands, outcomes, and audit records."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from fx_platform.domain.common import require_utc
from fx_platform.domain.execution import ExecutionStatus
from fx_platform.domain.market import AccountSnapshot, MarketSnapshot


class DecisionOutcomeStatus(StrEnum):
    """Stable high-level outcomes returned by the decision use case."""

    NO_SIGNAL = "no_signal"
    RISK_REJECTED = "risk_rejected"
    EXECUTION_REJECTED = "execution_rejected"
    PAPER_EXECUTED = "paper_executed"
    DUPLICATE = "duplicate"


class AuditStage(StrEnum):
    """Durable progress markers for the paper decision workflow."""

    REJECTED = "rejected"
    INTENT_CREATED = "intent_created"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionCommand:
    """Validated versioned request passed from the HTTP boundary."""

    request_id: UUID
    request_timestamp: datetime
    nonce: str
    schema_version: str
    node_id: str
    market: MarketSnapshot
    account: AccountSnapshot

    def __post_init__(self) -> None:
        require_utc(self.request_timestamp, "request_timestamp")
        if self.schema_version != "1.0":
            raise ValueError("unsupported schema version")
        if not self.nonce or not self.node_id:
            raise ValueError("nonce and node_id must not be empty")


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionOutcome:
    """Use-case result with trace identifiers and machine-readable reasons."""

    request_id: UUID
    status: DecisionOutcomeStatus
    signal_id: UUID | None
    risk_decision_id: UUID | None
    execution_id: UUID | None
    execution_status: ExecutionStatus | None
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionAuditRecord:
    """Minimal immutable audit snapshot sufficient to trace the bootstrap workflow."""

    decision_id: UUID
    nonce: str
    occurred_at: datetime
    stage: AuditStage
    node_id: str
    market_snapshot_id: UUID
    symbol: str
    strategy_name: str
    strategy_version: str
    signal_id: UUID | None
    ai_status: str
    risk_decision_id: UUID | None
    risk_approved: bool
    risk_reasons: tuple[str, ...]
    execution_id: UUID | None
    execution_status: str | None

    def __post_init__(self) -> None:
        require_utc(self.occurred_at, "occurred_at")
        if not self.nonce or not self.node_id or not self.symbol:
            raise ValueError("audit nonce, node_id, and symbol must not be empty")
