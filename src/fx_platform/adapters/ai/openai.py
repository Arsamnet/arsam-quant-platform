"""Structured OpenAI adapter boundary; no SDK or network client is created by default."""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError

from fx_platform.domain.advisory import AiAssessment, AiAssessmentStatus
from fx_platform.domain.common import TradeSide
from fx_platform.domain.market import MarketSnapshot
from fx_platform.domain.strategy import SignalCandidate


class AiProviderError(RuntimeError):
    """Expected provider/network failure translated into an unavailable assessment."""


class StructuredAiClient(Protocol):
    """Small client boundary implemented by a future OpenAI SDK integration."""

    def create_assessment(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        """Return only the strict structured schema documented below."""
        ...


def _decimal_string(value: object) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("AI decimal values must be JSON strings")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("invalid decimal string") from error
    if not parsed.is_finite():
        raise ValueError("decimal value must be finite")
    return parsed


ExactDecimal = Annotated[Decimal, BeforeValidator(_decimal_string)]


class _AiResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    direction_preference: Literal["buy", "sell", "neutral"]
    confidence: ExactDecimal = Field(ge=0, le=1)
    market_regime: Literal["trending", "ranging", "volatile", "uncertain"]
    uncertainty: ExactDecimal = Field(ge=0, le=1)
    reasoning_tags: tuple[str, ...] = Field(max_length=16)


class OpenAiAdvisor:
    """Validate bounded structured advice before creating a domain assessment."""

    def __init__(self, client: StructuredAiClient, model: str) -> None:
        if not model:
            raise ValueError("model must not be empty")
        self._client = client
        self._model = model

    def assess(
        self,
        *,
        assessment_id: UUID,
        evaluated_at: datetime,
        market: MarketSnapshot,
        signal: SignalCandidate,
    ) -> AiAssessment:
        """Call the injected client and fail closed on expected provider or schema failures."""
        payload: dict[str, object] = {
            "model": self._model,
            "schema_version": "1.0",
            "market": {
                "snapshot_id": str(market.snapshot_id),
                "symbol": market.symbol,
                "observed_at": market.observed_at.isoformat(),
                "bid": str(market.bid),
                "ask": str(market.ask),
                "previous_close": str(market.previous_close),
            },
            "candidate": {
                "signal_id": str(signal.signal_id),
                "side": signal.side.value,
                "entry_price": str(signal.entry_price),
            },
        }
        try:
            raw_response = self._client.create_assessment(payload)
        except AiProviderError:
            return self._failed_assessment(
                assessment_id,
                signal.signal_id,
                evaluated_at,
                AiAssessmentStatus.UNAVAILABLE,
                "ai_provider_unavailable",
            )

        try:
            response = _AiResponse.model_validate(raw_response)
            direction = (
                None
                if response.direction_preference == "neutral"
                else TradeSide(response.direction_preference)
            )
            return AiAssessment(
                assessment_id=assessment_id,
                signal_id=signal.signal_id,
                created_at=evaluated_at,
                status=AiAssessmentStatus.AVAILABLE,
                direction_preference=direction,
                confidence=response.confidence,
                market_regime=response.market_regime,
                uncertainty=response.uncertainty,
                reasoning_tags=response.reasoning_tags,
            )
        except (ValidationError, ValueError):
            return self._failed_assessment(
                assessment_id,
                signal.signal_id,
                evaluated_at,
                AiAssessmentStatus.INVALID,
                "ai_response_invalid",
            )

    @staticmethod
    def _failed_assessment(
        assessment_id: UUID,
        signal_id: UUID,
        evaluated_at: datetime,
        status: AiAssessmentStatus,
        tag: str,
    ) -> AiAssessment:
        return AiAssessment(
            assessment_id=assessment_id,
            signal_id=signal_id,
            created_at=evaluated_at,
            status=status,
            direction_preference=None,
            confidence=Decimal(0),
            market_regime="unknown",
            uncertainty=Decimal(1),
            reasoning_tags=(tag,),
        )
