"""Canonical JSON primitives for reproducible hashes and result bytes."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


def canonical_value(value: Any) -> Any:
    """Normalize supported values without floats or process-dependent ordering."""
    normalized: Any
    if value is None or isinstance(value, (bool, int, str)):
        normalized = value
    elif isinstance(value, Decimal):
        normalized = "0" if value == Decimal(0) else format(value.normalize(), "f")
    elif isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("canonical datetime must be timezone-aware UTC")
        normalized = value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    elif isinstance(value, timedelta):
        normalized = str(
            value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds
        )
    elif isinstance(value, UUID):
        normalized = str(value)
    elif isinstance(value, Enum):
        normalized = canonical_value(value.value)
    elif isinstance(value, Mapping):
        normalized = {str(key): canonical_value(item) for key, item in sorted(value.items())}
    elif isinstance(value, (set, frozenset)):
        normalized_items = [canonical_value(item) for item in value]
        normalized = sorted(normalized_items, key=canonical_json)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        normalized = [canonical_value(item) for item in value]
    else:
        raise TypeError(f"unsupported canonical value: {type(value).__name__}")
    return normalized


def canonical_json(value: Any) -> str:
    """Serialize one logical value to stable standards-compliant JSON."""
    return json.dumps(
        canonical_value(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def fingerprint(value: Any) -> str:
    """Return a SHA-256 fingerprint of canonical logical content."""
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()
