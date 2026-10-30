"""FastAPI composition and loopback-only paper/demo execution endpoints."""

import logging
from collections.abc import Awaitable, Callable
from time import perf_counter

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response

from fx_platform import __version__
from fx_platform.adapters.execution import (
    ExecutionStoreConflictError,
    ReconciliationRequiredError,
    SqliteDemoExecutionStore,
    intent_to_wire,
)
from fx_platform.application.factory import build_runtime
from fx_platform.application.service import DecisionService
from fx_platform.config import Settings
from fx_platform.domain.common import TradingMode
from fx_platform.observability import configure_logging

from .contracts import (
    DecisionRequest,
    DecisionResponse,
    DemoExecutionAck,
    DemoExecutionIntentResponse,
    DemoExecutionResultRequest,
    DemoExecutionStatusResponse,
    HealthResponse,
)
from .security import verify_local_token, verify_signature

logger = logging.getLogger(__name__)


def _hmac_dependency(settings: Settings) -> Callable[..., Awaitable[None]]:
    async def verify_request_hmac(
        request: Request,
        x_fx_signature: str | None = Header(default=None),
    ) -> None:
        secret = None if settings.hmac_secret is None else settings.hmac_secret.get_secret_value()
        if not verify_signature(await request.body(), x_fx_signature, secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid request authentication",
            )

    return verify_request_hmac


def _execution_token_dependency(settings: Settings) -> Callable[..., Awaitable[None]]:
    async def verify_execution_token(
        x_fx_execution_token: str | None = Header(default=None),
    ) -> None:
        secret = (
            None
            if settings.demo_execution_secret is None
            else settings.demo_execution_secret.get_secret_value()
        )
        if not verify_local_token(x_fx_execution_token, secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid execution authentication",
            )

    return verify_execution_token


def create_app(
    *,
    settings: Settings | None = None,
    service: DecisionService | None = None,
    demo_execution_store: SqliteDemoExecutionStore | None = None,
) -> FastAPI:
    """Create the local API with injectable deterministic dependencies for tests."""
    active_settings = settings or Settings()
    configure_logging(active_settings.log_level)
    if service is None:
        runtime = build_runtime(active_settings)
        decision_service = runtime.service
        active_demo_store = runtime.demo_execution_store
    else:
        decision_service = service
        active_demo_store = demo_execution_store
    verify_hmac = _hmac_dependency(active_settings)
    verify_execution_token = _execution_token_dependency(active_settings)

    application = FastAPI(
        title="Arsam Quant Platform Internal API",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
    )

    @application.middleware("http")
    async def request_log_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = perf_counter()
        response = await call_next(request)
        logger.info(
            "http_request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "elapsed_ms": round((perf_counter() - started) * 1000, 3),
            },
        )
        return response

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
        logger.error(
            "unexpected_request_failure",
            exc_info=(type(error), error, error.__traceback__),
            extra={"method": request.method, "path": request.url.path},
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "decision infrastructure unavailable; request rejected"},
        )

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            version=__version__,
            trading_mode=active_settings.trading_mode.value,
            ai_mode=active_settings.ai_mode.value,
            node_id=active_settings.active_node_id,
        )

    @application.post(
        "/v1/decision",
        response_model=DecisionResponse,
        dependencies=[Depends(verify_hmac)],
    )
    def decision(payload: DecisionRequest) -> DecisionResponse:
        outcome = decision_service.decide(payload.to_command())
        logger.info(
            "decision_completed",
            extra={
                "decision_id": str(outcome.request_id),
                "signal_id": None if outcome.signal_id is None else str(outcome.signal_id),
                "execution_id": None if outcome.execution_id is None else str(outcome.execution_id),
                "node_id": active_settings.active_node_id,
            },
        )
        return DecisionResponse.from_outcome(outcome)

    if active_settings.trading_mode is TradingMode.DEMO:
        if active_demo_store is None:
            raise RuntimeError("demo mode requires the durable execution store")

        @application.get(
            "/v1/demo-execution/next",
            response_model=DemoExecutionIntentResponse,
            dependencies=[Depends(verify_execution_token)],
            responses={
                204: {"description": "No pending intent"},
                409: {"description": "Reconcile"},
            },
        )
        def next_demo_execution() -> Response | dict[str, object]:
            try:
                intent = active_demo_store.claim_next(active_settings.active_node_id)
            except ReconciliationRequiredError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "reason": "reconciliation_required",
                        "execution_ids": [str(value) for value in error.execution_ids],
                    },
                ) from error
            if intent is None:
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            logger.info(
                "demo_execution_claimed",
                extra={
                    "execution_id": str(intent.execution_id),
                    "intent_id": str(intent.intent_id),
                    "node_id": intent.node_id,
                    "symbol": intent.symbol,
                    "side": intent.side.value,
                    "volume": str(intent.volume),
                },
            )
            return intent_to_wire(intent)

        def store_result(payload: DemoExecutionResultRequest) -> DemoExecutionAck:
            result = payload.to_domain()
            try:
                active_demo_store.record_result(result)
            except ExecutionStoreConflictError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="execution result rejected by durable state",
                ) from error
            logger.info(
                "demo_execution_result_recorded",
                extra={
                    "execution_id": str(result.execution_id),
                    "intent_id": str(result.intent_id),
                    "symbol": result.symbol,
                    "side": None if result.side is None else result.side.value,
                    "volume": None
                    if result.requested_volume is None
                    else str(result.requested_volume),
                    "broker_order_id": result.broker_order_id,
                    "broker_deal_id": result.broker_deal_id,
                    "retcode": result.broker_retcode,
                    "status": result.status.value,
                    "reconciliation_status": result.reconciliation_status.value,
                },
            )
            return DemoExecutionAck(
                execution_id=result.execution_id,
                status=result.status,
            )

        application.post(
            "/v1/demo-execution/result",
            response_model=DemoExecutionAck,
            dependencies=[Depends(verify_execution_token)],
        )(store_result)
        application.post(
            "/v1/demo-execution/reconcile",
            response_model=DemoExecutionAck,
            dependencies=[Depends(verify_execution_token)],
        )(store_result)

        @application.get(
            "/v1/demo-execution/status",
            response_model=DemoExecutionStatusResponse,
            dependencies=[Depends(verify_execution_token)],
        )
        def demo_execution_status() -> DemoExecutionStatusResponse:
            return DemoExecutionStatusResponse(
                execution_enabled=active_settings.demo_execution_enabled,
                node_id=active_settings.active_node_id,
                counts=active_demo_store.status_counts(),
            )

    return application


app = create_app()


def run() -> None:
    """Run the local API using validated loopback configuration."""
    settings = Settings()
    uvicorn.run(app, host=settings.bind_host, port=settings.bind_port)


if __name__ == "__main__":
    run()
