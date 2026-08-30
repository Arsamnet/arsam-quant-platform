"""Regression coverage for duplicate request/intent execution suppression."""

from fx_platform.application.models import DecisionOutcomeStatus
from tests.helpers import REQUEST_ID
from tests.unit.test_decision_service import _command, _service


def test_same_decision_cannot_execute_twice_after_completed_audit() -> None:
    service, executor, repository = _service()

    first = service.decide(_command())
    final_record = repository.get(REQUEST_ID)
    second = service.decide(_command())

    assert first.status is DecisionOutcomeStatus.PAPER_EXECUTED
    assert second.status is DecisionOutcomeStatus.DUPLICATE
    assert repository.get(REQUEST_ID) == final_record
    assert len(executor.executed_intents) == 1
