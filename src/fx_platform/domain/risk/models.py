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
    SYMBOL_SPECIFICATION_UNAVAILABLE = "symbol_specification_unavailable"
    SPREAD_POLICY_UNAVAILABLE = "spread_policy_unavailable"
    SPREAD_TOO_WIDE = "spread_too_wide"
    INVALID_VOLUME = "invalid_volume"
    VOLUME_BELOW_MINIMUM = "volume_below_minimum"
    VOLUME_LIMIT_EXCEEDED = "volume_limit_exceeded"
    VOLUME_STEP_MISMATCH = "volume_step_mismatch"
    MISSING_STOP_LOSS = "missing_stop_loss"
    INVALID_STOP_LOSS = "invalid_stop_loss"
    MISSING_TAKE_PROFIT = "missing_take_profit"
    INVALID_TAKE_PROFIT = "invalid_take_profit"
    POSITION_LIMIT_EXCEEDED = "position_limit_exceeded"
    DAILY_LOSS_LIMIT_EXCEEDED = "daily_loss_limit_exceeded"
    AI_REQUIRED = "ai_required"
    AI_DIRECTION_REQUIRED = "ai_direction_required"
    AI_DIRECTION_CONFLICT = "ai_direction_conflict"
    AI_CONFIDENCE_TOO_LOW = "ai_confidence_too_low"
    AI_UNCERTAINTY_TOO_HIGH = "ai_uncertainty_too_high"
    TRADE_RISK_LIMIT_EXCEEDED = "trade_risk_limit_exceeded"
    CONVERSION_RATE_UNAVAILABLE = "conversion_rate_unavailable"
    CONVERSION_RATE_AMBIGUOUS = "conversion_rate_ambiguous"
    CONVERSION_RATE_STALE = "conversion_rate_stale"
    CONVERSION_RATE_IN_FUTURE = "conversion_rate_in_future"
    HIGH_IMPACT_EVENT_BLACKOUT = "high_impact_event_blackout"
    CALENDAR_REQUIRED = "calendar_required"


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskLimits:
    """Conservative bootstrap limits; changes are safety-sensitive."""

    allowed_symbols: frozenset[str]
    max_volume: Decimal = Decimal("0.10")
    max_open_positions: int = 3
    max_daily_loss_fraction: Decimal = Decimal("0.02")
    max_daily_loss_absolute_cap: Decimal | None = Decimal(200)
    max_trade_risk_fraction: Decimal = Decimal("0.01")
    max_market_age: timedelta = timedelta(seconds=30)
    max_account_age: timedelta = timedelta(seconds=30)
    max_signal_age: timedelta = timedelta(seconds=15)
    max_conversion_age: timedelta = timedelta(seconds=30)
    max_future_skew: timedelta = timedelta(seconds=2)
    ai_required: bool = False
    ai_min_confidence: Decimal = Decimal("0.60")
    ai_max_uncertainty: Decimal = Decimal("0.50")
    economic_calendar_required: bool = False
    require_take_profit: bool = False
    event_blackout_before: timedelta = timedelta(minutes=15)
    event_blackout_after: timedelta = timedelta(minutes=15)

    def __post_init__(self) -> None:
        if not self.allowed_symbols or any(
            not symbol or symbol != symbol.upper() for symbol in self.allowed_symbols
        ):
            raise ValueError("allowed_symbols must contain uppercase symbols")
        for field_name, decimal_value in (
            ("max_volume", self.max_volume),
            ("max_daily_loss_fraction", self.max_daily_loss_fraction),
            ("max_trade_risk_fraction", self.max_trade_risk_fraction),
        ):
            require_positive_decimal(decimal_value, field_name)
        if self.max_daily_loss_absolute_cap is not None:
            require_positive_decimal(
                self.max_daily_loss_absolute_cap,
                "max_daily_loss_absolute_cap",
            )
        for field_name, fraction in (
            ("max_daily_loss_fraction", self.max_daily_loss_fraction),
            ("max_trade_risk_fraction", self.max_trade_risk_fraction),
            ("ai_min_confidence", self.ai_min_confidence),
            ("ai_max_uncertainty", self.ai_max_uncertainty),
        ):
            require_finite_decimal(fraction, field_name)
            if fraction < Decimal(0) or fraction > Decimal(1):
                raise ValueError(f"{field_name} must be between zero and one")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least one")
        for field_name, duration in (
            ("max_market_age", self.max_market_age),
            ("max_account_age", self.max_account_age),
            ("max_signal_age", self.max_signal_age),
            ("max_conversion_age", self.max_conversion_age),
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
    maximum_daily_loss_amount: Decimal

    def __post_init__(self) -> None:
        require_utc(self.evaluated_at, "evaluated_at")
        require_positive_decimal(self.maximum_risk_amount, "maximum_risk_amount")
        require_positive_decimal(
            self.maximum_daily_loss_amount,
            "maximum_daily_loss_amount",
        )
        if self.calculated_risk_amount is not None:
            require_finite_decimal(self.calculated_risk_amount, "calculated_risk_amount")
        if self.approved == bool(self.reasons):
            raise ValueError(
                "approved decisions have no reasons; rejected decisions require reasons"
            )
