"""Deterministic advisor used when AI is explicitly disabled."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fx_platform.domain.advisory import AiAssessment, AiAssessmentStatus
from fx_platform.domain.market import MarketSnapshot
from fx_platform.domain.strategy import SignalCandidate


class NullAiAdvisor:
    """Return an explicit disabled state without making a network call."""

    def assess(
        self,
        *,
        assessment_id: UUID,
        evaluated_at: datetime,
        market: MarketSnapshot,
        signal: SignalCandidate,
    ) -> AiAssessment:
        """Return a neutral deterministic assessment tied to the candidate signal."""
        del market
        return AiAssessment(
            assessment_id=assessment_id,
            signal_id=signal.signal_id,
            created_at=evaluated_at,
            status=AiAssessmentStatus.DISABLED,
            direction_preference=None,
            confidence=Decimal(0),
            market_regime="not_assessed",
            uncertainty=Decimal(1),
            reasoning_tags=("ai_explicitly_disabled",),
        )
