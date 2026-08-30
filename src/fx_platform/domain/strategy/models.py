"""Strategy output models; candidates remain subject to independent risk approval."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fx_platform.domain.common import TradeSide, require_finite_decimal, require_utc


@dataclass(frozen=True, slots=True, kw_only=True)
class SignalCandidate:
    """A non-executable strategy proposal evaluated later by the risk engine."""

    signal_id: UUID
    market_snapshot_id: UUID
    strategy_name: str
    strategy_version: str
    created_at: datetime
    symbol: str
    side: TradeSide
    entry_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    volume: Decimal

    def __post_init__(self) -> None:
        require_utc(self.created_at, "created_at")
        require_finite_decimal(self.entry_price, "entry_price")
        require_finite_decimal(self.volume, "volume")
        if self.stop_loss is not None:
            require_finite_decimal(self.stop_loss, "stop_loss")
        if self.take_profit is not None:
            require_finite_decimal(self.take_profit, "take_profit")
        if not self.strategy_name or not self.strategy_version:
            raise ValueError("strategy identity must not be empty")
        if not self.symbol or self.symbol != self.symbol.upper():
            raise ValueError("symbol must be non-empty uppercase text")


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyDecision:
    """Deterministic strategy result, including explicit no-signal outcomes."""

    strategy_name: str
    strategy_version: str
    evaluated_at: datetime
    candidate: SignalCandidate | None
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        require_utc(self.evaluated_at, "evaluated_at")
        if not self.strategy_name or not self.strategy_version:
            raise ValueError("strategy identity must not be empty")
        if self.candidate is None and not self.reasons:
            raise ValueError("a no-signal decision requires a reason")
