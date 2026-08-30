"""Application workflow tests proving fail-closed non-invocation behavior."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from fx_platform.adapters.ai import NullAiAdvisor
from fx_platform.adapters.economic import NullEconomicCalendarProvider
from fx_platform.adapters.execution import FakeExecutionAdapter
from fx_platform.adapters.market import StaticSymbolSpecificationProvider
from fx_platform.adapters.persistence import InMemoryAuditRepository
from fx_platform.application.models import (
    AuditStage,
    DecisionCommand,
    DecisionOutcomeStatus,
)
from fx_platform.application.service import DecisionService
from fx_platform.domain.common import TradingMode
from fx_platform.domain.execution import ExecutionStatus
from fx_platform.domain.risk import RiskEngine, RiskLimits
from fx_platform.domain.strategy import PreviousCloseMomentumStrategy
from tests.helpers import (
    NOW,
    REQUEST_ID,
    FixedClock,
    make_account,
    make_market,
    make_specification,
)


@dataclass(slots=True)
class _SequenceClock:
    values: list[datetime]

    def now(self) -> datetime:
        return self.values.pop(0)


def _command(
    *,
    request_id: UUID = REQUEST_ID,
    nonce: str = "nonce_1234567890",
    timestamp: datetime = NOW,
    node_id: str = "paper-node",
    previous_close: Decimal = Decimal("1.0990"),
    spread_ask: Decimal = Decimal("1.1002"),
    symbol: str = "EURUSD",
    daily_realized_pnl: Decimal = Decimal(0),
    open_position_count: int = 0,
) -> DecisionCommand:
    return DecisionCommand(
        request_id=request_id,
        request_timestamp=timestamp,
        nonce=nonce,
        schema_version="1.0",
        node_id=node_id,
        market=make_market(
            symbol=symbol,
            ask=spread_ask,
            previous_close=previous_close,
        ),
        account=make_account(
            daily_realized_pnl=daily_realized_pnl,
            open_position_count=open_position_count,
        ),
    )


def _service(
    *,
    clock=None,
    repository=None,
    advisor=None,
    strategy=None,
    risk_engine=None,
    calendar=None,
    symbol_specifications=None,
    economic_calendar_required: bool = False,
):
    active_clock = clock or FixedClock()
    executor = FakeExecutionAdapter(active_clock)
    audit_repository = repository or InMemoryAuditRepository()
    service = DecisionService(
        node_id="paper-node",
        trading_mode=TradingMode.PAPER,
        clock=active_clock,
        strategy=strategy or PreviousCloseMomentumStrategy(),
        symbol_specifications=symbol_specifications
        or StaticSymbolSpecificationProvider((make_specification(),)),
        ai_advisor=advisor or NullAiAdvisor(),
        risk_engine=risk_engine
        or RiskEngine(
            RiskLimits(
                allowed_symbols=frozenset({"EURUSD"}),
                economic_calendar_required=economic_calendar_required,
            )
        ),
        calendar=calendar or NullEconomicCalendarProvider(),
        executor=executor,
        audit_repository=audit_repository,
    )
    return service, executor, audit_repository


def test_approved_candidate_reaches_paper_executor_and_final_audit() -> None:
    service, executor, repository = _service()

    outcome = service.decide(_command())
    record = repository.get(REQUEST_ID)

    assert outcome.status is DecisionOutcomeStatus.PAPER_EXECUTED
    assert outcome.execution_status is ExecutionStatus.PAPER_FILLED
    assert len(executor.executed_intents) == 1
    assert record is not None
    assert record.stage is AuditStage.COMPLETED
    assert record.risk_approved
    assert record.execution_status == ExecutionStatus.PAPER_FILLED.value


def test_risk_rejection_never_reaches_execution_adapter() -> None:
    service, executor, repository = _service()

    outcome = service.decide(_command(spread_ask=Decimal("1.1010")))

    assert outcome.status is DecisionOutcomeStatus.RISK_REJECTED
    assert "spread_too_wide" in outcome.reasons
    assert executor.executed_intents == ()
    assert repository.get(REQUEST_ID).stage is AuditStage.REJECTED


def test_combined_risk_failures_are_reported_without_an_execution_id() -> None:
    service, executor, _ = _service()

    outcome = service.decide(
        _command(
            spread_ask=Decimal("1.1010"),
            daily_realized_pnl=Decimal(-200),
            open_position_count=3,
        )
    )

    assert {
        "spread_too_wide",
        "daily_loss_limit_exceeded",
        "position_limit_exceeded",
    }.issubset(outcome.reasons)
    assert outcome.execution_id is None
    assert executor.executed_intents == ()


def test_no_signal_is_audited_without_ai_risk_or_execution() -> None:
    service, executor, repository = _service()

    outcome = service.decide(_command(previous_close=Decimal("1.1001")))

    assert outcome.status is DecisionOutcomeStatus.NO_SIGNAL
    assert outcome.reasons == ("midpoint_equals_previous_close",)
    assert executor.executed_intents == ()
    assert repository.get(REQUEST_ID).ai_status == "not_requested"


def test_duplicate_request_id_or_nonce_is_suppressed_before_execution() -> None:
    service, executor, _ = _service()
    first = service.decide(_command())

    repeated_id = service.decide(_command())
    repeated_nonce = service.decide(_command(request_id=uuid4()))

    assert first.status is DecisionOutcomeStatus.PAPER_EXECUTED
    assert repeated_id.status is DecisionOutcomeStatus.DUPLICATE
    assert repeated_nonce.status is DecisionOutcomeStatus.DUPLICATE
    assert len(executor.executed_intents) == 1


def test_wrong_node_and_stale_or_future_requests_are_rejected_before_strategy() -> None:
    cases = (
        (_command(node_id="other-node"), "node_id_mismatch"),
        (_command(timestamp=NOW - timedelta(minutes=1)), "request_stale"),
        (_command(timestamp=NOW + timedelta(seconds=3)), "request_timestamp_in_future"),
    )

    for command, reason in cases:
        service, executor, repository = _service()
        outcome = service.decide(command)
        assert outcome.status is DecisionOutcomeStatus.RISK_REJECTED
        assert outcome.reasons == (reason,)
        assert outcome.signal_id is None
        assert outcome.risk_decision_id is None
        assert outcome.execution_id is None
        assert executor.executed_intents == ()
        assert repository.get(command.request_id).risk_reasons == (reason,)


def test_required_unavailable_calendar_rejects_without_execution() -> None:
    service, executor, _ = _service(economic_calendar_required=True)

    outcome = service.decide(_command())

    assert outcome.status is DecisionOutcomeStatus.RISK_REJECTED
    assert "calendar_required" in outcome.reasons
    assert executor.executed_intents == ()


def test_expired_intent_is_reported_as_execution_rejection() -> None:
    clock = _SequenceClock([NOW, NOW + timedelta(seconds=10), NOW + timedelta(seconds=10)])
    service, executor, repository = _service(clock=clock)

    outcome = service.decide(_command())

    assert outcome.status is DecisionOutcomeStatus.EXECUTION_REJECTED
    assert outcome.execution_status is ExecutionStatus.REJECTED
    assert executor.executed_intents == ()
    assert repository.get(REQUEST_ID).execution_status == ExecutionStatus.REJECTED.value


class _UnavailableRepository:
    def get(self, decision_id: UUID):
        del decision_id
        raise RuntimeError("audit unavailable")

    def get_by_nonce(self, nonce: str):
        del nonce
        raise RuntimeError("audit unavailable")

    def save(self, record) -> None:
        del record
        raise RuntimeError("audit unavailable")


def test_audit_state_unavailable_fails_before_execution() -> None:
    service, executor, _ = _service(repository=_UnavailableRepository())

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.decide(_command())

    assert executor.executed_intents == ()


class _ExplodingAdvisor:
    def assess(self, **kwargs):
        del kwargs
        raise RuntimeError("unexpected advisor failure")


class _NeverCalledStrategy:
    name = "never_called"
    version = "1.0.0"

    def evaluate(self, *args, **kwargs):
        del args, kwargs
        raise AssertionError("strategy must not be called")


class _NeverCalledCalendar:
    def events_for(self, **kwargs):
        del kwargs
        raise AssertionError("calendar must not be called")


class _NeverCalledRiskEngine:
    def evaluate(self, **kwargs):
        del kwargs
        raise AssertionError("risk engine must not be called")


def test_unknown_symbol_is_rejected_before_strategy_and_all_downstream_calls() -> None:
    service, executor, repository = _service(
        strategy=_NeverCalledStrategy(),
        advisor=_ExplodingAdvisor(),
        calendar=_NeverCalledCalendar(),
        risk_engine=_NeverCalledRiskEngine(),
    )

    outcome = service.decide(_command(symbol="XAUUSD"))

    assert outcome.status is DecisionOutcomeStatus.RISK_REJECTED
    assert outcome.reasons == ("unknown_symbol",)
    assert outcome.signal_id is None
    assert outcome.risk_decision_id is None
    assert outcome.execution_id is None
    assert executor.executed_intents == ()
    assert repository.get(REQUEST_ID).ai_status == "not_requested"


def test_missing_required_currency_conversion_never_creates_execution_intent() -> None:
    usd_jpy = make_specification(
        symbol="USDJPY",
        base_currency="USD",
        quote_currency="JPY",
        tick_size=Decimal("0.001"),
        tick_value=Decimal(100),
        tick_value_currency="JPY",
    )
    service, executor, _ = _service(
        risk_engine=RiskEngine(RiskLimits(allowed_symbols=frozenset({"USDJPY"}))),
        symbol_specifications=StaticSymbolSpecificationProvider((usd_jpy,)),
    )

    outcome = service.decide(_command(symbol="USDJPY"))

    assert outcome.reasons == ("conversion_rate_unavailable",)
    assert outcome.execution_id is None
    assert executor.executed_intents == ()


def test_unexpected_advisor_exception_never_becomes_approval() -> None:
    service, executor, _ = _service(advisor=_ExplodingAdvisor())

    with pytest.raises(RuntimeError, match="advisor failure"):
        service.decide(_command())

    assert executor.executed_intents == ()


def test_service_constructor_rejects_live_mode_and_empty_node() -> None:
    clock = FixedClock()
    executor = FakeExecutionAdapter(clock)
    common = {
        "clock": clock,
        "strategy": PreviousCloseMomentumStrategy(),
        "symbol_specifications": StaticSymbolSpecificationProvider((make_specification(),)),
        "ai_advisor": NullAiAdvisor(),
        "risk_engine": RiskEngine(RiskLimits(allowed_symbols=frozenset({"EURUSD"}))),
        "calendar": NullEconomicCalendarProvider(),
        "executor": executor,
        "audit_repository": InMemoryAuditRepository(),
    }
    with pytest.raises(ValueError, match="paper"):
        DecisionService(node_id="paper-node", trading_mode=TradingMode.LIVE, **common)
    with pytest.raises(ValueError, match="node_id"):
        DecisionService(node_id="", trading_mode=TradingMode.PAPER, **common)
