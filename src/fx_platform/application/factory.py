"""Composition root for the safe in-memory bootstrap runtime."""

from dataclasses import dataclass

from fx_platform.adapters.ai import NullAiAdvisor
from fx_platform.adapters.clock import SystemClock
from fx_platform.adapters.economic import NullEconomicCalendarProvider
from fx_platform.adapters.execution import FakeExecutionAdapter
from fx_platform.adapters.persistence import InMemoryAuditRepository
from fx_platform.application.service import DecisionService
from fx_platform.config import AiMode, Settings
from fx_platform.domain.risk import RiskEngine, RiskLimits
from fx_platform.domain.strategy import PreviousCloseMomentumStrategy


@dataclass(frozen=True, slots=True)
class Runtime:
    """Inspectable local runtime components without global mutable state."""

    service: DecisionService
    executor: FakeExecutionAdapter
    audit_repository: InMemoryAuditRepository


def build_runtime(settings: Settings) -> Runtime:
    """Build a paper-only local runtime with no broker or remote AI connectivity."""
    if settings.ai_mode is not AiMode.DISABLED:
        raise RuntimeError(
            "The OpenAI client is an adapter boundary only; inject a reviewed client explicitly"
        )
    clock = SystemClock()
    executor = FakeExecutionAdapter(clock)
    audit_repository = InMemoryAuditRepository()
    risk_engine = RiskEngine(
        RiskLimits(
            allowed_symbols=settings.allowed_symbols,
            max_volume=settings.max_volume,
            max_open_positions=settings.max_open_positions,
            max_daily_loss=settings.max_daily_loss,
            max_trade_risk_fraction=settings.max_trade_risk_fraction,
            max_spread=settings.max_spread,
            ai_required=settings.ai_required,
            economic_calendar_required=settings.economic_calendar_required,
        )
    )
    service = DecisionService(
        node_id=settings.node_id,
        trading_mode=settings.trading_mode,
        clock=clock,
        strategy=PreviousCloseMomentumStrategy(),
        ai_advisor=NullAiAdvisor(),
        risk_engine=risk_engine,
        calendar=NullEconomicCalendarProvider(),
        executor=executor,
        audit_repository=audit_repository,
    )
    return Runtime(service=service, executor=executor, audit_repository=audit_repository)
