"""Immutable execution values downstream of explicit risk approval."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from fx_platform.domain.common import (
    TradeSide,
    TradingMode,
    require_finite_decimal,
    require_positive_decimal,
    require_utc,
)

_SHA256_HEX_LENGTH = 64


class OrderType(StrEnum):
    """Order types reviewed for guarded execution."""

    MARKET = "market"


class ExecutionStatus(StrEnum):
    """Fail-closed paper, outbox, broker, and reconciliation states."""

    PAPER_FILLED = "paper_filled"
    PENDING = "pending"
    CLAIMED = "claimed"
    SUBMITTED = "submitted"
    REJECTED = "rejected"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    POSITION_CONFIRMED = "position_confirmed"
    RECONCILIATION_FAILED = "reconciliation_failed"
    UNKNOWN = "unknown"
    DUPLICATE = "duplicate"


class ReconciliationStatus(StrEnum):
    """Independent statement about broker-state verification."""

    NOT_STARTED = "not_started"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    UNKNOWN = "unknown"


def _require_sha256(value: str, field_name: str) -> None:
    if len(value) != _SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionIntent:
    """Risk-approved instruction consumed by paper or guarded demo execution."""

    schema_version: str
    execution_id: UUID
    intent_id: UUID
    request_id: UUID
    signal_id: UUID
    risk_decision_id: UUID
    created_at: datetime
    expires_at: datetime
    node_id: str
    symbol: str
    side: TradeSide
    order_type: OrderType
    volume: Decimal
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal | None
    maximum_spread: Decimal
    risk_fingerprint: str
    request_fingerprint: str
    nonce: str
    strategy_name: str
    strategy_version: str
    trading_mode: TradingMode

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("unsupported execution intent schema version")
        require_utc(self.created_at, "created_at")
        require_utc(self.expires_at, "expires_at")
        require_positive_decimal(self.volume, "volume")
        require_positive_decimal(self.entry_price, "entry_price")
        require_positive_decimal(self.stop_loss, "stop_loss")
        require_positive_decimal(self.maximum_spread, "maximum_spread")
        if self.take_profit is not None:
            require_positive_decimal(self.take_profit, "take_profit")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")
        if self.trading_mode is TradingMode.LIVE:
            raise ValueError("live execution intents are forbidden")
        if self.trading_mode is TradingMode.DEMO and self.take_profit is None:
            raise ValueError("demo execution intents require take_profit")
        if self.order_type is not OrderType.MARKET:
            raise ValueError("only market execution is supported")
        identity = (
            self.node_id,
            self.symbol,
            self.nonce,
            self.strategy_name,
            self.strategy_version,
        )
        if not all(identity):
            raise ValueError("execution identity fields must not be empty")
        _require_sha256(self.risk_fingerprint, "risk_fingerprint")
        _require_sha256(self.request_fingerprint, "request_fingerprint")

    @property
    def decision_id(self) -> UUID:
        """Compatibility alias for the original paper execution contract."""
        return self.request_id

    @property
    def requested_price(self) -> Decimal:
        """Expose the audit-oriented wire name for a market reference price."""
        return self.entry_price


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionResult:
    """Paper or broker result with explicit reconciliation state."""

    execution_id: UUID
    completed_at: datetime
    status: ExecutionStatus
    message: str
    intent_id: UUID | None = None
    broker_retcode: int | None = None
    broker_retcode_description: str | None = None
    broker_order_id: int | None = None
    broker_deal_id: int | None = None
    requested_volume: Decimal | None = None
    filled_volume: Decimal | None = None
    requested_price: Decimal | None = None
    executed_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    submitted_at: datetime | None = None
    executed_at: datetime | None = None
    reported_at: datetime | None = None
    symbol: str | None = None
    side: TradeSide | None = None
    reconciliation_status: ReconciliationStatus = ReconciliationStatus.NOT_STARTED

    def __post_init__(self) -> None:
        require_utc(self.completed_at, "completed_at")
        for field_name in ("submitted_at", "executed_at", "reported_at"):
            value = getattr(self, field_name)
            if value is not None:
                require_utc(value, field_name)
        for field_name in (
            "requested_volume",
            "filled_volume",
            "requested_price",
            "executed_price",
            "stop_loss",
            "take_profit",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_finite_decimal(value, field_name)
                if value < Decimal(0):
                    raise ValueError(f"{field_name} must not be negative")
        if not self.message:
            raise ValueError("message must not be empty")
        if self.status is ExecutionStatus.POSITION_CONFIRMED and (
            self.reconciliation_status is not ReconciliationStatus.CONFIRMED
        ):
            raise ValueError("position_confirmed requires confirmed reconciliation")
        self._validate_broker_status()

    def _validate_broker_status(self) -> None:
        broker_fill_statuses = {
            ExecutionStatus.FILLED,
            ExecutionStatus.PARTIALLY_FILLED,
            ExecutionStatus.POSITION_CONFIRMED,
        }
        if self.status in broker_fill_statuses:
            if self.filled_volume is None or self.filled_volume <= Decimal(0):
                raise ValueError("broker fill status requires positive filled_volume")
            if self.executed_price is None or self.executed_price <= Decimal(0):
                raise ValueError("broker fill status requires positive executed_price")
            if not any(
                identifier is not None and identifier > 0
                for identifier in (self.broker_order_id, self.broker_deal_id)
            ):
                raise ValueError("broker fill status requires a positive broker identifier")
        if self.status is ExecutionStatus.SUBMITTED and (
            self.broker_order_id is None or self.broker_order_id <= 0
        ):
            raise ValueError("submitted status requires a positive broker order identifier")
        if self.status is ExecutionStatus.REJECTED and self.filled_volume not in {
            None,
            Decimal(0),
        }:
            raise ValueError("rejected status cannot report filled volume")
