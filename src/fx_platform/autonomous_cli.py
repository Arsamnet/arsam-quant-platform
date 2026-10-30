"""Windows/local autonomous DEMO supervisor entry point."""

import argparse
import logging
import time
from datetime import timedelta

from fx_platform.adapters.clock import SystemClock
from fx_platform.adapters.market.autonomous import FileAutonomousSnapshotSource
from fx_platform.application.autonomy import AutonomousDemoSupervisor, AutonomousSnapshotError
from fx_platform.application.factory import build_runtime
from fx_platform.config import Settings
from fx_platform.observability import configure_logging

logger = logging.getLogger(__name__)


def build_autonomous_supervisor(settings: Settings) -> AutonomousDemoSupervisor:
    """Compose the autonomous loop from reviewed local-only boundaries."""
    if not settings.autonomous_demo_enabled:
        raise RuntimeError("FX_AUTONOMOUS_DEMO_ENABLED=true is required")
    runtime = build_runtime(settings)
    if runtime.demo_execution_store is None:
        raise RuntimeError("autonomous DEMO requires the durable demo execution store")
    source = FileAutonomousSnapshotSource(
        path=settings.autonomous_snapshot_path,
        expected_broker_company=settings.demo_expected_broker_company,
        expected_broker_server=settings.demo_expected_broker_server,
        expected_account_currency=settings.demo_expected_account_currency,
        expected_leverage=settings.demo_expected_leverage,
        allowed_symbols=settings.demo_allowed_symbols,
        account_id=settings.autonomous_account_id,
        max_tick_age_seconds=settings.autonomous_max_snapshot_age_seconds,
    )
    return AutonomousDemoSupervisor(
        service=runtime.service,
        source=source,
        execution_state=runtime.demo_execution_store,
        clock=SystemClock(),
        node_id=settings.active_node_id,
        allowed_symbols=settings.demo_allowed_symbols,
        max_snapshot_age=timedelta(seconds=settings.autonomous_max_snapshot_age_seconds),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run guarded AI-assisted autonomous trading against the reviewed DEMO account."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Evaluate at most one snapshot cycle and exit without retrying.",
    )
    return parser


def main() -> None:
    """Run the fail-closed autonomous loop; LIVE remains forbidden by Settings."""
    args = _parser().parse_args()
    settings = Settings()
    configure_logging(settings.log_level)
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
