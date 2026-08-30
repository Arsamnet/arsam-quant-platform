"""Economic calendar values suitable for point-in-time risk evaluation."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from fx_platform.domain.common import require_finite_decimal, require_utc


class EventImportance(StrEnum):
    """Normalized scheduled-event impact classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True, kw_only=True)
class EconomicEvent:
    """A versioned point-in-time calendar event; later revisions need a new dataset version."""

    event_id: UUID
    name: str
    scheduled_at: datetime
    importance: EventImportance
    currencies: frozenset[str]
    source_version: str
    actual: Decimal | None = None
    forecast: Decimal | None = None
    previous: Decimal | None = None

    def __post_init__(self) -> None:
        require_utc(self.scheduled_at, "scheduled_at")
        if not self.name or not self.source_version:
            raise ValueError("event name and source version must not be empty")
        if not self.currencies or any(currency != currency.upper() for currency in self.currencies):
            raise ValueError("currencies must be non-empty uppercase codes")
        for field_name, value in (
            ("actual", self.actual),
            ("forecast", self.forecast),
            ("previous", self.previous),
        ):
            if value is not None:
                require_finite_decimal(value, field_name)
