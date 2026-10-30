"""Composition root for paper execution or the guarded local demo outbox."""

from dataclasses import dataclass
from datetime import timedelta

from fx_platform.adapters.ai import (
    NullAiAdvisor,
    OpenAiAdvisor,
    OpenAiResponsesClient,
    StructuredAiClient,
)
from fx_platform.adapters.clock import SystemClock
from fx_platform.adapters.economic import NullEconomicCalendarProvider
from fx_platform.adapters.execution import FakeExecutionAdapter, SqliteDemoExecutionStore
from fx_platform.adapters.market import bootstrap_symbol_specifications
from fx_platform.adapters.persistence import InMemoryAuditRepository
from fx_platform.application.ports import AiAdvisor, ExecutionAdapter
from fx_platform.application.service import DecisionService
from fx_platform.config import AiMode, Settings
from fx_platform.domain.common import TradingMode
from fx_platform.domain.risk import RiskEngine, RiskLimits
from fx_platform.domain.strategy import PreviousCloseMomentumStrategy


@dataclass(frozen=True, slots=True)
class Runtime:
    """Inspectable local runtime components without global mutable state."""

    service: DecisionService
    executor: ExecutionAdapter
    audit_repository: InMemoryAuditRepository
    demo_execution_store: SqliteDemoExecutionStore | None


def build_runtime(
    settings: Settings,
    *,
    ai_client: StructuredAiClient | None = None,
) -> Runtime:
    """Build the local paper/demo runtime without granting AI execution authority."""
    clock = SystemClock()
    demo_store = None
    if settings.trading_mode is TradingMode.DEMO:
        demo_store = SqliteDemoExecutionStore(settings.demo_outbox_path, clock)
        executor: ExecutionAdapter = demo_store
    else:
        executor = FakeExecutionAdapter(clock)

    ai_advisor: AiAdvisor
    if settings.ai_mode is AiMode.DISABLED:
        ai_advisor = NullAiAdvisor()
    else:
        api_key = settings.openai_api_key
        model = settings.openai_model
        if api_key is None or model is None:
            raise RuntimeError("validated OpenAI settings unexpectedly missing")
        client = ai_client or OpenAiResponsesClient(
            api_key=api_key.get_secret_value(),
            model=model,
            timeout_seconds=settings.openai_timeout_seconds,
        )
        ai_advisor = OpenAiAdvisor(client, model)

    audit_repository = InMemoryAuditRepository()
    risk_engine = RiskEngine(
        RiskLimits(
            allowed_symbols=(
                settings.demo_allowed_symbols
                if settings.trading_mode is TradingMode.DEMO
                else settings.allowed_symbols
            ),
            max_volume=(
                settings.demo_max_volume
                if settings.trading_mode is TradingMode.DEMO
                else settings.max_volume
            ),
            max_open_positions=(
                settings.demo_max_open_positions
                if settings.trading_mode is TradingMode.DEMO
                else settings.max_open_positions
            ),
            max_daily_loss_fraction=settings.max_daily_loss_fraction,
            max_daily_loss_absolute_cap=settings.max_daily_loss_absolute_cap,
            max_trade_risk_fraction=settings.max_trade_risk_fraction,
            ai_required=settings.ai_required,
            economic_calendar_required=settings.economic_calendar_required,
            require_take_profit=(
                settings.demo_require_take_profit
                if settings.trading_mode is TradingMode.DEMO
                else False
            ),
        )
    )
    service = DecisionService(
        node_id=settings.active_node_id,
        trading_mode=settings.trading_mode,
        clock=clock,
        strategy=PreviousCloseMomentumStrategy(),
        symbol_specifications=bootstrap_symbol_specifications(
            settings.demo_allowed_symbols
            if settings.trading_mode is TradingMode.DEMO
            else settings.allowed_symbols
        ),
        ai_advisor=ai_advisor,
        risk_engine=risk_engine,
        calendar=NullEconomicCalendarProvider(),
        executor=executor,
        audit_repository=audit_repository,
        intent_ttl=timedelta(seconds=settings.demo_request_ttl_seconds)
        if settings.trading_mode is TradingMode.DEMO
        else timedelta(seconds=10),
    )
    return Runtime(
        service=service,
        executor=executor,
        audit_repository=audit_repository,
        demo_execution_store=demo_store,
    )
