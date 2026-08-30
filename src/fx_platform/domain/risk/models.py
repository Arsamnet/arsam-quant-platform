"""Risk configuration and auditable decision values."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from fx_platform.domain.common import require_finite_decimal, require_positive_decimal, require_utc


class RiskRejection(StrEnum):
    """Stable machine-readable risk rejection reasons."""

    NON_PAPER_MODE = "non_paper_mode"
    UNKNOWN_SYMBOL = "unknown_symbol"
    MARKET_DATA_STALE = "market_data_stale"
    MARKET_DATA_IN_FUTURE = "market_data_in_future"
    MARKET_SNAPSHOT_MISMATCH = "market_snapshot_mismatch"
    ACCOUNT_DATA_STALE = "account_data_stale"
    ACCOUNT_DATA_IN_FUTURE = "account_data_in_future"
    SIGNAL_STALE = "signal_stale"
    SIGNAL_IN_FUTURE = "signal_in_future"
    SPREAD_TOO_WIDE = "spread_too_wide"
    INVALID_VOLUME = "invalid_volume"
    VOLUME_LIMIT_EXCEEDED = "volume_limit_exceeded"
    MISSING_STOP_LOSS = "missing_stop_loss"
    INVALID_STOP_LOSS = "invalid_stop_loss"
    POSITION_LIMIT_EXCEEDED = "position_limit_exceeded"
    DAILY_LOSS_LIMIT_EXCEEDED = "daily_loss_limit_exceeded"
    AI_REQUIRED = "ai_required"
    AI_DIRECTION_CONFLICT = "ai_direction_conflict"
    TRADE_RISK_LIMIT_EXCEEDED = "trade_risk_limit_exceeded"
    HIGH_IMPACT_EVENT_BLACKOUT = "high_impact_event_blackout"
    CALENDAR_REQUIRED = "calendar_required"


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskLimits:
    """Conservative bootstrap limits; changes are safety-sensitive."""

    allowed_symbols: frozenset[str]
    max_volume: Decimal = Decimal("0.10")
    max_open_positions: int = 3
    max_daily_loss: Decimal = Decimal(200)
    max_trade_risk_fraction: Decimal = Decimal("0.01")
    max_market_age: timedelta = timedelta(seconds=30)
    max_account_age: timedelta = timedelta(seconds=30)
    max_signal_age: timedelta = timedelta(seconds=15)
    max_future_skew: timedelta = timedelta(seconds=2)
    max_spread: Decimal = Decimal("0.0005")
    contract_size: Decimal = Decimal(100000)
    ai_required: bool = False
    economic_calendar_required: bool = False
    event_blackout_before: timedelta = timedelta(minutes=15)
    event_blackout_after: timedelta = timedelta(minutes=15)

    def __post_init__(self) -> None:
        if not self.allowed_symbols or any(
            not symbol or symbol != symbol.upper() for symbol in self.allowed_symbols
        ):
            raise ValueError("allowed_symbols must contain uppercase symbols")
        for field_name, decimal_value in (
            ("max_volume", self.max_volume),
            ("max_daily_loss", self.max_daily_loss),
            ("max_trade_risk_fraction", self.max_trade_risk_fraction),
            ("max_spread", self.max_spread),
            ("contract_size", self.contract_size),
        ):
            require_positive_decimal(decimal_value, field_name)
        if self.max_trade_risk_fraction > Decimal(1):
            raise ValueError("max_trade_risk_fraction must not exceed one")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least one")
        for field_name, duration in (
            ("max_market_age", self.max_market_age),
            ("max_account_age", self.max_account_age),
            ("max_signal_age", self.max_signal_age),
            ("max_future_skew", self.max_future_skew),
            ("event_blackout_before", self.event_blackout_before),
            ("event_blackout_after", self.event_blackout_after),
        ):
            if duration < timedelta(0):
                message = f"{field_name} must not be negative"
                raise ValueError(message)


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskDecision:
    """Auditable result of evaluating a candidate against every available rule."""

    risk_decision_id: UUID
    signal_id: UUID
    evaluated_at: datetime
    approved: bool
    reasons: tuple[RiskRejection, ...]
    calculated_risk_amount: Decimal | None
    maximum_risk_amount: Decimal

    def __post_init__(self) -> None:
        require_utc(self.evaluated_at, "evaluated_at")
        require_positive_decimal(self.maximum_risk_amount, "maximum_risk_amount")
        if self.calculated_risk_amount is not None:
            require_finite_decimal(self.calculated_risk_amount, "calculated_risk_amount")
        if self.approved == bool(self.reasons):
            raise ValueError(
                "approved decisions have no reasons; rejected decisions require reasons"
            )
