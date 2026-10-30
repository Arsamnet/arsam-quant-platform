"""Windows/local autonomous DEMO supervisor entry point."""

import argparse
import json
import logging
import time
from datetime import timedelta
from uuid import UUID, uuid5

from fx_platform.adapters.ai import OpenAiAdvisor, OpenAiResponsesClient, StructuredAiClient
from fx_platform.adapters.clock import SystemClock
from fx_platform.adapters.market import bootstrap_symbol_specifications
from fx_platform.adapters.market.autonomous import FileAutonomousSnapshotSource
from fx_platform.application.autonomy import (
    AutonomousDemoSupervisor,
    AutonomousSnapshot,
    AutonomousSnapshotError,
)
from fx_platform.application.factory import build_runtime
from fx_platform.config import AiMode, Settings
from fx_platform.domain.advisory import AiAssessment, AiAssessmentStatus
from fx_platform.domain.strategy import PreviousCloseMomentumStrategy
from fx_platform.observability import configure_logging

logger = logging.getLogger(__name__)
_AI_VALIDATION_NAMESPACE = UUID("d613d8ca-e9ef-4df4-94e1-d7d54b4356ae")


def build_snapshot_source(settings: Settings) -> FileAutonomousSnapshotSource:
    """Build the strict local MT5 snapshot boundary without starting trading logic."""
    return FileAutonomousSnapshotSource(
        path=settings.autonomous_snapshot_path,
        expected_broker_company=settings.demo_expected_broker_company,
        expected_broker_server=settings.demo_expected_broker_server,
        expected_account_currency=settings.demo_expected_account_currency,
        expected_leverage=settings.demo_expected_leverage,
        allowed_symbols=settings.demo_allowed_symbols,
        account_id=settings.autonomous_account_id,
        max_tick_age_seconds=settings.autonomous_max_snapshot_age_seconds,
    )


def read_fresh_snapshot(settings: Settings) -> AutonomousSnapshot:
    """Read one local snapshot and enforce wall-clock freshness before any AI call."""
    snapshot = build_snapshot_source(settings).read()
    now = SystemClock().now()
    if snapshot.acquired_at - now > timedelta(seconds=2):
        raise AutonomousSnapshotError("autonomous snapshot timestamp is in the future")
    if now - snapshot.acquired_at > timedelta(seconds=settings.autonomous_max_snapshot_age_seconds):
        raise AutonomousSnapshotError("autonomous snapshot is stale")
    if snapshot.account.observed_at != snapshot.acquired_at:
        raise AutonomousSnapshotError("account observation does not match snapshot acquisition")
    return snapshot


def build_autonomous_supervisor(settings: Settings) -> AutonomousDemoSupervisor:
    """Compose the autonomous loop from reviewed local-only boundaries."""
    if not settings.autonomous_demo_enabled:
        raise RuntimeError("FX_AUTONOMOUS_DEMO_ENABLED=true is required")
    runtime = build_runtime(settings)
    if runtime.demo_execution_store is None:
        raise RuntimeError("autonomous DEMO requires the durable demo execution store")
    return AutonomousDemoSupervisor(
        service=runtime.service,
        source=build_snapshot_source(settings),
        execution_state=runtime.demo_execution_store,
        clock=SystemClock(),
        node_id=settings.active_node_id,
        allowed_symbols=settings.demo_allowed_symbols,
        max_snapshot_age=timedelta(seconds=settings.autonomous_max_snapshot_age_seconds),
    )


def validate_ai_only(
    settings: Settings,
    *,
    symbol: str,
    ai_client: StructuredAiClient | None = None,
) -> AiAssessment:
    """Validate one real OpenAI advisory without risk, outbox, or execution access."""
    if settings.ai_mode is not AiMode.OPENAI:
        raise RuntimeError("AI-only validation requires FX_AI_MODE=openai")
    api_key = settings.openai_api_key
    model = settings.openai_model
    if api_key is None or model is None:
        raise RuntimeError("validated OpenAI settings unexpectedly missing")
    if symbol not in settings.demo_allowed_symbols:
        raise RuntimeError(f"AI validation symbol is not in the reviewed allowlist: {symbol}")

    snapshot = read_fresh_snapshot(settings)
    observation = next(
        (item for item in snapshot.markets if item.market.symbol == symbol),
        None,
    )
    if observation is None:
        raise RuntimeError(f"AI validation snapshot has no market observation for {symbol}")

    specification = bootstrap_symbol_specifications(settings.demo_allowed_symbols).get(symbol)
    if specification is None:
        raise RuntimeError(f"symbol specification unavailable for AI validation: {symbol}")

    strategy = PreviousCloseMomentumStrategy()
    identity = (
        f"ai-validation:{settings.active_node_id}:{symbol}:"
        f"{observation.decision_bar_time.isoformat()}"
    )
    signal_id = uuid5(_AI_VALIDATION_NAMESPACE, identity + ":signal")
    decision = strategy.evaluate(
        observation.market,
        specification,
        signal_id=signal_id,
        evaluated_at=snapshot.acquired_at,
    )
    if decision.candidate is None:
        raise RuntimeError(
            "AI-only validation requires a deterministic strategy candidate for the current snapshot"
        )

    client = ai_client or OpenAiResponsesClient(
        api_key=api_key.get_secret_value(),
        model=model,
        timeout_seconds=settings.openai_timeout_seconds,
    )
    advisor = OpenAiAdvisor(client, model)
    return advisor.assess(
        assessment_id=uuid5(_AI_VALIDATION_NAMESPACE, identity + ":assessment"),
        evaluated_at=snapshot.acquired_at,
        market=observation.market,
        signal=decision.candidate,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run guarded AI-assisted autonomous trading against the reviewed DEMO account."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="Evaluate at most one decision cycle and exit without retrying.",
    )
    mode.add_argument(
        "--validate-snapshot",
        action="store_true",
        help="Validate the local MT5 snapshot and exit without AI, risk, or execution.",
    )
    mode.add_argument(
        "--validate-ai",
        metavar="SYMBOL",
        choices=("EURUSD", "GBPUSD", "USDJPY"),
        help="Call OpenAI for one symbol and exit without risk, outbox, or execution.",
    )
    return parser


def main() -> None:
    """Run the fail-closed autonomous loop; LIVE remains forbidden by Settings."""
    args = _parser().parse_args()
    settings = Settings()
    configure_logging(settings.log_level)

    if args.validate_snapshot:
        snapshot = read_fresh_snapshot(settings)
        logger.info(
            "autonomous_snapshot_valid",
            extra={
                "symbols": ",".join(sorted(item.market.symbol for item in snapshot.markets)),
                "open_position_count": snapshot.account.open_position_count,
            },
        )
        return

    if args.validate_ai is not None:
        assessment = validate_ai_only(settings, symbol=args.validate_ai)
        output = {
            "mode": "ai_only_validation",
            "symbol": args.validate_ai,
            "status": assessment.status.value,
            "direction_preference": (
                None
                if assessment.direction_preference is None
                else assessment.direction_preference.value
            ),
            "confidence": str(assessment.confidence),
            "market_regime": assessment.market_regime,
            "uncertainty": str(assessment.uncertainty),
            "reasoning_tags": list(assessment.reasoning_tags),
            "risk_engine_called": False,
            "outbox_called": False,
            "execution_called": False,
        }
        print(json.dumps(output, separators=(",", ":"), sort_keys=True))
        if assessment.status is not AiAssessmentStatus.AVAILABLE:
            raise SystemExit(3)
        return

    supervisor = build_autonomous_supervisor(settings)
    logger.info(
        "autonomous_demo_started",
        extra={
            "node_id": settings.active_node_id,
            "symbols": ",".join(sorted(settings.demo_allowed_symbols)),
            "ai_mode": settings.ai_mode.value,
        },
    )

    while True:
        try:
            outcomes = supervisor.run_cycle()
        except AutonomousSnapshotError as error:
            logger.warning(
                "autonomous_snapshot_rejected",
                extra={"reason": str(error)},
            )
            outcomes = ()

        for outcome in outcomes:
            logger.info(
                "autonomous_decision_completed",
                extra={
                    "decision_id": str(outcome.request_id),
                    "execution_id": (
                        None if outcome.execution_id is None else str(outcome.execution_id)
                    ),
                    "status": outcome.status.value,
                    "reasons": ",".join(outcome.reasons),
                },
            )

        if args.once:
            return
        time.sleep(settings.autonomous_poll_interval_seconds)


if __name__ == "__main__":
    main()
