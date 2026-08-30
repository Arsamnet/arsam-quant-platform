"""Constrained AI advisory values accepted by deterministic domain logic."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from fx_platform.domain.common import TradeSide, require_finite_decimal, require_utc

_MAX_REASONING_TAGS = 16
_MAX_REASONING_TAG_LENGTH = 64


class AiAssessmentStatus(StrEnum):
    """Trust state of an AI assessment."""

    DISABLED = "disabled"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True, kw_only=True)
class AiAssessment:
    """Validated, bounded advisory data without order-placement authority."""

    assessment_id: UUID
    signal_id: UUID
    created_at: datetime
    status: AiAssessmentStatus
    direction_preference: TradeSide | None
    confidence: Decimal
    market_regime: str
    uncertainty: Decimal
    reasoning_tags: tuple[str, ...]

    def __post_init__(self) -> None:
        require_utc(self.created_at, "created_at")
        require_finite_decimal(self.confidence, "confidence")
        require_finite_decimal(self.uncertainty, "uncertainty")
        if not Decimal(0) <= self.confidence <= Decimal(1):
            raise ValueError("confidence must be between zero and one")
        if not Decimal(0) <= self.uncertainty <= Decimal(1):
            raise ValueError("uncertainty must be between zero and one")
        if len(self.reasoning_tags) > _MAX_REASONING_TAGS:
            raise ValueError("reasoning_tags may contain at most 16 values")
        if any(not tag or len(tag) > _MAX_REASONING_TAG_LENGTH for tag in self.reasoning_tags):
            raise ValueError("reasoning_tags must be non-empty and at most 64 characters")
