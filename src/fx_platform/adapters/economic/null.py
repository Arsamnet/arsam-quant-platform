"""Deterministic disabled calendar provider."""

from dataclasses import dataclass
from datetime import datetime

from fx_platform.domain.economic import EconomicEvent


@dataclass(frozen=True, slots=True)
class CalendarData:
    """Normalized provider availability and point-in-time events."""

    available: bool
    events: tuple[EconomicEvent, ...]


class NullEconomicCalendarProvider:
    """Represent an explicitly unconfigured calendar without a network call."""

    def events_for(
        self,
        *,
        symbol: str,
        window_start: datetime,
        window_end: datetime,
    ) -> CalendarData:
        """Return no events and explicit unavailable status."""
        del symbol, window_start, window_end
        return CalendarData(available=False, events=())
