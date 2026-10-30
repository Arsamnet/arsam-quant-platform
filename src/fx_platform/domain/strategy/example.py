"""A deliberately simple deterministic strategy used to prove architecture."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fx_platform.domain.common import TradeSide, require_positive_decimal, require_utc
from fx_platform.domain.market import MarketSnapshot, SymbolSpecification
from fx_platform.domain.strategy.models import SignalCandidate, StrategyDecision


@dataclass(frozen=True, slots=True, kw_only=True)
class PreviousCloseMomentumStrategy:
    """Compare the current midpoint with the supplied point-in-time previous close.

    This strategy exists solely to exercise the system boundaries and makes no profitability claim.
    """

    volume: Decimal = Decimal("0.01")
    stop_distance_ticks: Decimal = Decimal(100)
    reward_to_risk: Decimal = Decimal(2)
    name: str = "previous_close_momentum_example"
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        require_positive_decimal(self.volume, "volume")
        require_positive_decimal(self.stop_distance_ticks, "stop_distance_ticks")
        require_positive_decimal(self.reward_to_risk, "reward_to_risk")

    def evaluate(
        self,
        market: MarketSnapshot,
        symbol_specification: SymbolSpecification,
        *,
        signal_id: UUID,
        evaluated_at: datetime,
    ) -> StrategyDecision:
        """Produce the same candidate for the same snapshot and supplied identifiers."""
        require_utc(evaluated_at, "evaluated_at")
        if symbol_specification.symbol != market.symbol:
            raise ValueError("symbol specification does not match market symbol")
        mid_price = market.mid_price
        if mid_price == market.previous_close:
            return StrategyDecision(
                strategy_name=self.name,
                strategy_version=self.version,
                evaluated_at=evaluated_at,
                candidate=None,
                reasons=("midpoint_equals_previous_close",),
            )

        side = TradeSide.BUY if mid_price > market.previous_close else TradeSide.SELL
        entry_price = market.ask if side is TradeSide.BUY else market.bid
        direction = Decimal(1) if side is TradeSide.BUY else Decimal(-1)
        stop_distance = symbol_specification.tick_size * self.stop_distance_ticks
        stop_loss = entry_price - (direction * stop_distance)
        take_profit = entry_price + (direction * stop_distance * self.reward_to_risk)
        candidate = SignalCandidate(
            signal_id=signal_id,
            market_snapshot_id=market.snapshot_id,
            strategy_name=self.name,
            strategy_version=self.version,
            created_at=evaluated_at,
            symbol=market.symbol,
            side=side,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=self.volume,
        )
        return StrategyDecision(
            strategy_name=self.name,
            strategy_version=self.version,
            evaluated_at=evaluated_at,
            candidate=candidate,
            reasons=("midpoint_above_previous_close",)
            if side is TradeSide.BUY
            else ("midpoint_below_previous_close",),
        )
