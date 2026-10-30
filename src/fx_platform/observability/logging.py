"""JSON logs that intentionally omit headers, bodies, and configuration secrets."""

import json
import logging
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """Serialize a constrained set of operational log fields."""

    _OPTIONAL_FIELDS = (
        "request_id",
        "method",
        "path",
        "status_code",
        "elapsed_ms",
        "decision_id",
        "run_id",
        "dataset_id",
        "signal_id",
        "risk_decision_id",
        "execution_id",
        "intent_id",
        "symbol",
        "side",
        "volume",
        "broker_order_id",
        "broker_deal_id",
        "retcode",
        "status",
        "reconciliation_status",
        "trade_id",
        "node_id",
        "snapshot_fingerprint",
        "contract_fingerprint",
        "validation_symbol",
        "validation_status",
    )

    def format(self, record: logging.LogRecord) -> str:
        """Format without serializing arbitrary record attributes or request data."""
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field_name in self._OPTIONAL_FIELDS:
            value = getattr(record, field_name, None)
            if value is not None:
                payload[field_name] = value
        if record.exc_info is not None and record.exc_info[0] is not None:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging(level: str) -> None:
    """Configure one structured stderr handler for the application root logger."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
