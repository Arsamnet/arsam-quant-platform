"""External-boundary adapter behavior without network or broker access."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from fx_platform.adapters.ai import AiProviderError, NullAiAdvisor, OpenAiAdvisor
from fx_platform.adapters.economic import NullEconomicCalendarProvider
from fx_platform.adapters.execution import FakeExecutionAdapter
from fx_platform.adapters.persistence import InMemoryAuditRepository
from fx_platform.application.models import AuditStage, DecisionAuditRecord
from fx_platform.domain.advisory import AiAssessmentStatus
from fx_platform.domain.common import TradeSide, TradingMode
from fx_platform.domain.execution import ExecutionIntent, ExecutionStatus, OrderType
from tests.helpers import (
    ASSESSMENT_ID,
    NOW,
    REQUEST_ID,
    SIGNAL_ID,
    FixedClock,
    make_market,
    make_signal,
)


class _AiClient:
    def __init__(self, response: dict[str, object] | None = None, *, unavailable: bool = False):
        self.response = response or {}
        self.unavailable = unavailable
        self.payload: object = None

    def create_assessment(self, payload: object) -> dict[str, object]:
        self.payload = payload
        if self.unavailable:
            raise AiProviderError
        return self.response


def test_null_ai_advisor_is_deterministic_and_explicitly_disabled() -> None:
    assessment = NullAiAdvisor().assess(
        assessment_id=ASSESSMENT_ID,
        evaluated_at=NOW,
        market=make_market(),
        signal=make_signal(),
    )

    assert assessment.status is AiAssessmentStatus.DISABLED
    assert assessment.signal_id == SIGNAL_ID
    assert assessment.confidence == Decimal(0)


def test_openai_adapter_accepts_only_bounded_structured_output() -> None:
    client = _AiClient(
        {
            "direction_preference": "buy",
            "confidence": "0.75",
            "market_regime": "trending",
            "uncertainty": "0.25",
            "reasoning_tags": ("trend_alignment",),
        }
    )
    advisor = OpenAiAdvisor(client, "configured-model")

    assessment = advisor.assess(
        assessment_id=ASSESSMENT_ID,
        evaluated_at=NOW,
        market=make_market(),
        signal=make_signal(),
    )

    assert assessment.status is AiAssessmentStatus.AVAILABLE
    assert assessment.direction_preference is TradeSide.BUY
    assert assessment.confidence == Decimal("0.75")
    assert isinstance(client.payload, dict)
    assert "news" not in client.payload


@pytest.mark.parametrize(
    "response",
    [
        {},
        {
            "direction_preference": "buy",
            "confidence": 0.75,
            "market_regime": "trending",
            "uncertainty": "0.25",
            "reasoning_tags": (),
        },
        {
            "direction_preference": "execute_now",
            "confidence": "0.75",
            "market_regime": "trending",
            "uncertainty": "0.25",
            "reasoning_tags": (),
            "lot_size": "1000",
        },
    ],
)
def test_openai_adapter_marks_invalid_output_without_execution_authority(
    response: dict[str, object],
) -> None:
    assessment = OpenAiAdvisor(_AiClient(response), "configured-model").assess(
        assessment_id=ASSESSMENT_ID,
        evaluated_at=NOW,
        market=make_market(),
        signal=make_signal(),
    )

    assert assessment.status is AiAssessmentStatus.INVALID
    assert assessment.direction_preference is None


def test_openai_provider_failure_becomes_unavailable_assessment() -> None:
    assessment = OpenAiAdvisor(_AiClient(unavailable=True), "configured-model").assess(
        assessment_id=ASSESSMENT_ID,
        evaluated_at=NOW,
        market=make_market(),
        signal=make_signal(),
    )

    assert assessment.status is AiAssessmentStatus.UNAVAILABLE


def test_openai_adapter_requires_configured_model() -> None:
    with pytest.raises(ValueError, match="model"):
        OpenAiAdvisor(_AiClient(), "")


def test_null_calendar_is_explicitly_unavailable() -> None:
    result = NullEconomicCalendarProvider().events_for(
        symbol="EURUSD",
        window_start=NOW - timedelta(minutes=15),
        window_end=NOW + timedelta(minutes=15),
    )

    assert not result.available
    assert result.events == ()


def _intent() -> ExecutionIntent:
    return ExecutionIntent(
        schema_version="1.0",
        execution_id=uuid4(),
        intent_id=uuid4(),
        request_id=REQUEST_ID,
        signal_id=SIGNAL_ID,
        risk_decision_id=uuid4(),
        created_at=NOW,
        expires_at=NOW + timedelta(seconds=10),
        node_id="paper-node",
        symbol="EURUSD",
        side=TradeSide.BUY,
        order_type=OrderType.MARKET,
        volume=Decimal("0.01"),
        entry_price=Decimal("1.1002"),
        stop_loss=Decimal("1.0992"),
        take_profit=Decimal("1.1022"),
        maximum_spread=Decimal("0.00050"),
        risk_fingerprint="0" * 64,
        request_fingerprint="1" * 64,
        nonce="nonce_1234567890",
        strategy_name="test_strategy",
        strategy_version="1.0.0",
        trading_mode=TradingMode.PAPER,
    )


def test_fake_executor_records_once_and_suppresses_duplicate() -> None:
    adapter = FakeExecutionAdapter(FixedClock())
    intent = _intent()

    first = adapter.execute(intent)
    duplicate = adapter.execute(intent)

    assert first.status is ExecutionStatus.PAPER_FILLED
    assert duplicate.status is ExecutionStatus.DUPLICATE
    assert adapter.executed_intents == (intent,)


def test_fake_executor_rejects_expired_intent() -> None:
    adapter = FakeExecutionAdapter(FixedClock(NOW + timedelta(seconds=10)))

    result = adapter.execute(_intent())

    assert result.status is ExecutionStatus.REJECTED
    assert adapter.executed_intents == ()


def _audit_record(*, decision_id=REQUEST_ID, nonce: str = "nonce_1234567890"):
    return DecisionAuditRecord(
        decision_id=decision_id,
        nonce=nonce,
        occurred_at=NOW,
        stage=AuditStage.REJECTED,
        node_id="paper-node",
        market_snapshot_id=make_market().snapshot_id,
        symbol="EURUSD",
        strategy_name="fixture",
        strategy_version="1",
        signal_id=None,
        ai_status="not_requested",
        risk_decision_id=None,
        risk_approved=False,
        risk_reasons=("fixture",),
        execution_id=None,
        execution_status=None,
    )


def test_memory_audit_repository_indexes_decision_and_nonce() -> None:
    repository = InMemoryAuditRepository()
    record = _audit_record()

    repository.save(record)

    assert repository.get(record.decision_id) == record
    assert repository.get_by_nonce(record.nonce) == record
    assert repository.get(uuid4()) is None
    assert repository.get_by_nonce("unknown") is None


def test_memory_audit_repository_rejects_nonce_reuse() -> None:
    repository = InMemoryAuditRepository()
    repository.save(_audit_record())

    with pytest.raises(ValueError, match="nonce"):
        repository.save(_audit_record(decision_id=uuid4()))
