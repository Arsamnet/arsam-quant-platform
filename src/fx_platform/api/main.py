"""FastAPI composition and loopback-only paper decision endpoints."""

import logging
from collections.abc import Awaitable, Callable
from time import perf_counter

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response

from fx_platform import __version__
from fx_platform.application.factory import build_runtime
from fx_platform.application.service import DecisionService
from fx_platform.config import Settings
from fx_platform.observability import configure_logging

from .contracts import DecisionRequest, DecisionResponse, HealthResponse
from .security import verify_signature

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


def create_app(
    *,
    settings: Settings | None = None,
    service: DecisionService | None = None,
) -> FastAPI:
    """Create the local API with injectable deterministic dependencies for tests."""
    active_settings = settings or Settings()
    configure_logging(active_settings.log_level)
    decision_service = service or build_runtime(active_settings).service
    verify_hmac = _hmac_dependency(active_settings)

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
            ai_mode=active_settings.ai_mode.value,
            node_id=active_settings.node_id,
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
                "node_id": active_settings.node_id,
            },
        )
        return DecisionResponse.from_outcome(outcome)

    return application


app = create_app()


def run() -> None:
    """Run the local API using validated loopback configuration."""
    settings = Settings()
    uvicorn.run(app, host=settings.bind_host, port=settings.bind_port)


if __name__ == "__main__":
    run()
