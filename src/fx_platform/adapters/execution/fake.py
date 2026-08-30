"""Thread-safe in-memory paper execution adapter."""

from threading import Lock
from uuid import UUID

from fx_platform.application.ports import Clock
from fx_platform.domain.execution import ExecutionIntent, ExecutionResult, ExecutionStatus


class FakeExecutionAdapter:
    """Record paper intents exactly once; this adapter cannot reach a broker."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._executed: dict[UUID, ExecutionIntent] = {}
        self._lock = Lock()

    @property
    def executed_intents(self) -> tuple[ExecutionIntent, ...]:
        """Return an immutable observation for tests and diagnostics."""
        with self._lock:
            return tuple(self._executed.values())

    def execute(self, intent: ExecutionIntent) -> ExecutionResult:
        """Reject expired intents and identify duplicate execution IDs."""
        now = self._clock.now()
        with self._lock:
            if intent.execution_id in self._executed:
                return ExecutionResult(
                    execution_id=intent.execution_id,
                    completed_at=now,
                    status=ExecutionStatus.DUPLICATE,
                    message="duplicate paper execution suppressed",
                )
            if now >= intent.expires_at:
                return ExecutionResult(
                    execution_id=intent.execution_id,
                    completed_at=now,
                    status=ExecutionStatus.REJECTED,
                    message="paper execution intent expired",
                )
            self._executed[intent.execution_id] = intent
        return ExecutionResult(
            execution_id=intent.execution_id,
            completed_at=now,
            status=ExecutionStatus.PAPER_FILLED,
            message="paper execution recorded; no broker order was sent",
        )
