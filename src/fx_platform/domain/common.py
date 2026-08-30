"""Shared domain value types and invariant helpers."""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum


class TradingMode(StrEnum):
    """Supported configuration values; only paper is authorized in this phase."""

    PAPER = "paper"
    DEMO = "demo"
    LIVE = "live"


class TradeSide(StrEnum):
    """Direction of an FX trade candidate."""

    BUY = "buy"
    SELL = "sell"


def require_utc(value: datetime, field_name: str) -> None:
    """Reject naive and non-UTC timestamps at the domain boundary."""
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        message = f"{field_name} must be timezone-aware UTC"
        raise ValueError(message)


def require_finite_decimal(value: Decimal, field_name: str) -> None:
    """Reject NaN and infinity, which make financial comparisons unsafe."""
    if not value.is_finite():
        message = f"{field_name} must be finite"
        raise ValueError(message)


def require_positive_decimal(value: Decimal, field_name: str) -> None:
    """Require a finite decimal greater than zero."""
    require_finite_decimal(value, field_name)
    if value <= Decimal(0):
        message = f"{field_name} must be greater than zero"
        raise ValueError(message)
