"""Deterministic fail-closed risk evaluation."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fx_platform.domain.advisory import AiAssessment, AiAssessmentStatus
from fx_platform.domain.common import TradeSide, TradingMode, require_utc
from fx_platform.domain.economic import EconomicEvent, EventImportance
from fx_platform.domain.market import AccountSnapshot, MarketSnapshot
from fx_platform.domain.risk.models import RiskDecision, RiskLimits, RiskRejection
from fx_platform.domain.strategy import SignalCandidate


class RiskEngine:
    """Apply deterministic safety policy without infrastructure dependencies."""

    def __init__(self, limits: RiskLimits) -> None:
        self._limits = limits

    def evaluate(
        self,
        *,
        risk_decision_id: UUID,
        evaluated_at: datetime,
        trading_mode: TradingMode,
        market: MarketSnapshot,
        account: AccountSnapshot,
        signal: SignalCandidate,
        ai_assessment: AiAssessment,
        economic_events: tuple[EconomicEvent, ...],
        calendar_available: bool,
    ) -> RiskDecision:
        """Evaluate all applicable rules and return a non-executable decision value."""
        require_utc(evaluated_at, "evaluated_at")
        reasons: list[RiskRejection] = []

        if trading_mode is not TradingMode.PAPER:
            reasons.append(RiskRejection.NON_PAPER_MODE)
        if signal.symbol not in self._limits.allowed_symbols or signal.symbol != market.symbol:
            reasons.append(RiskRejection.UNKNOWN_SYMBOL)
        if signal.market_snapshot_id != market.snapshot_id:
            reasons.append(RiskRejection.MARKET_SNAPSHOT_MISMATCH)
        self._check_age(reasons, evaluated_at, market, account, signal)
        if market.spread > self._limits.max_spread:
            reasons.append(RiskRejection.SPREAD_TOO_WIDE)
        self._check_volume_and_stop(reasons, signal)
        if account.open_position_count >= self._limits.max_open_positions:
            reasons.append(RiskRejection.POSITION_LIMIT_EXCEEDED)
        if account.daily_realized_pnl <= -self._limits.max_daily_loss:
            reasons.append(RiskRejection.DAILY_LOSS_LIMIT_EXCEEDED)
        self._check_ai(reasons, signal, ai_assessment)
        self._check_economic_events(
            reasons,
            signal,
            evaluated_at,
            economic_events,
            calendar_available,
        )

        maximum_risk = account.balance * self._limits.max_trade_risk_fraction
        calculated_risk = self._calculate_risk(signal)
        if calculated_risk is not None and calculated_risk > maximum_risk:
            reasons.append(RiskRejection.TRADE_RISK_LIMIT_EXCEEDED)

        unique_reasons = tuple(dict.fromkeys(reasons))
        return RiskDecision(
            risk_decision_id=risk_decision_id,
            signal_id=signal.signal_id,
            evaluated_at=evaluated_at,
            approved=not unique_reasons,
            reasons=unique_reasons,
            calculated_risk_amount=calculated_risk,
            maximum_risk_amount=maximum_risk,
        )

    def _check_age(
        self,
        reasons: list[RiskRejection],
        now: datetime,
        market: MarketSnapshot,
        account: AccountSnapshot,
        signal: SignalCandidate,
    ) -> None:
        if market.observed_at - now > self._limits.max_future_skew:
            reasons.append(RiskRejection.MARKET_DATA_IN_FUTURE)
        if now - market.observed_at > self._limits.max_market_age:
            reasons.append(RiskRejection.MARKET_DATA_STALE)
        if now - account.observed_at > self._limits.max_account_age:
            reasons.append(RiskRejection.ACCOUNT_DATA_STALE)
        if account.observed_at - now > self._limits.max_future_skew:
            reasons.append(RiskRejection.ACCOUNT_DATA_IN_FUTURE)
        if now - signal.created_at > self._limits.max_signal_age:
            reasons.append(RiskRejection.SIGNAL_STALE)
        if signal.created_at - now > self._limits.max_future_skew:
            reasons.append(RiskRejection.SIGNAL_IN_FUTURE)

    def _check_volume_and_stop(
        self,
        reasons: list[RiskRejection],
        signal: SignalCandidate,
    ) -> None:
        if signal.volume <= Decimal(0):
            reasons.append(RiskRejection.INVALID_VOLUME)
        elif signal.volume > self._limits.max_volume:
            reasons.append(RiskRejection.VOLUME_LIMIT_EXCEEDED)

        if signal.stop_loss is None:
            reasons.append(RiskRejection.MISSING_STOP_LOSS)
        elif (signal.side is TradeSide.BUY and signal.stop_loss >= signal.entry_price) or (
            signal.side is TradeSide.SELL and signal.stop_loss <= signal.entry_price
        ):
            reasons.append(RiskRejection.INVALID_STOP_LOSS)

    def _check_ai(
        self,
        reasons: list[RiskRejection],
        signal: SignalCandidate,
        assessment: AiAssessment,
    ) -> None:
        if assessment.signal_id != signal.signal_id:
            reasons.append(RiskRejection.AI_REQUIRED)
            return
        if assessment.status in {
            AiAssessmentStatus.INVALID,
            AiAssessmentStatus.UNAVAILABLE,
        } or (self._limits.ai_required and assessment.status is not AiAssessmentStatus.AVAILABLE):
            reasons.append(RiskRejection.AI_REQUIRED)
        if (
            assessment.status is AiAssessmentStatus.AVAILABLE
            and assessment.direction_preference is not None
            and assessment.direction_preference is not signal.side
        ):
            reasons.append(RiskRejection.AI_DIRECTION_CONFLICT)

    def _check_economic_events(
        self,
        reasons: list[RiskRejection],
        signal: SignalCandidate,
        now: datetime,
        events: tuple[EconomicEvent, ...],
        calendar_available: bool,
    ) -> None:
        if self._limits.economic_calendar_required and not calendar_available:
            reasons.append(RiskRejection.CALENDAR_REQUIRED)
        symbol_currencies = frozenset((signal.symbol[:3], signal.symbol[3:6]))
        for event in events:
            blackout_start = event.scheduled_at - self._limits.event_blackout_before
            blackout_end = event.scheduled_at + self._limits.event_blackout_after
            if (
                event.importance is EventImportance.HIGH
                and event.currencies & symbol_currencies
                and blackout_start <= now <= blackout_end
            ):
                reasons.append(RiskRejection.HIGH_IMPACT_EVENT_BLACKOUT)
                break

    def _calculate_risk(self, signal: SignalCandidate) -> Decimal | None:
        if signal.stop_loss is None or signal.volume <= Decimal(0):
            return None
        distance = abs(signal.entry_price - signal.stop_loss)
        return distance * signal.volume * self._limits.contract_size
