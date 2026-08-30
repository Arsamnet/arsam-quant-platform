"""Paper-only execution values downstream of explicit risk approval."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from fx_platform.domain.common import (
    TradeSide,
    TradingMode,
    require_positive_decimal,
    require_utc,
)


class ExecutionStatus(StrEnum):
    """Paper adapter result status."""

    PAPER_FILLED = "paper_filled"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionIntent:
    """A paper-only intent that must originate from an approved risk decision."""

    execution_id: UUID
    decision_id: UUID
    signal_id: UUID
    risk_decision_id: UUID
    created_at: datetime
    expires_at: datetime
    node_id: str
    symbol: str
    side: TradeSide
    volume: Decimal
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal | None
    trading_mode: TradingMode

    def __post_init__(self) -> None:
        require_utc(self.created_at, "created_at")
        require_utc(self.expires_at, "expires_at")
        require_positive_decimal(self.volume, "volume")
        require_positive_decimal(self.entry_price, "entry_price")
        require_positive_decimal(self.stop_loss, "stop_loss")
        if self.take_profit is not None:
            require_positive_decimal(self.take_profit, "take_profit")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")
        if self.trading_mode is not TradingMode.PAPER:
            raise ValueError("only paper execution intents are supported")
        if not self.node_id or not self.symbol:
            raise ValueError("node_id and symbol must not be empty")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionResult:
    """Result returned by a paper execution boundary."""

    execution_id: UUID
    completed_at: datetime
    status: ExecutionStatus
    message: str

    def __post_init__(self) -> None:
        require_utc(self.completed_at, "completed_at")
        if not self.message:
            raise ValueError("message must not be empty")
