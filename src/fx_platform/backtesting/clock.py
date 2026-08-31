"""Historical clock controlled only by ordered simulation events."""

from dataclasses import dataclass
from datetime import datetime

from fx_platform.domain.common import require_utc


@dataclass(slots=True)
class BacktestClock:
    """A monotonic UTC clock that cannot read or move with wall time."""

    _current: datetime

    def __post_init__(self) -> None:
        require_utc(self._current, "initial backtest time")

    def now(self) -> datetime:
        """Return the current logical simulation instant."""
        return self._current

    def advance_to(self, value: datetime) -> None:
        """Advance monotonically; backward historical events are invalid."""
        require_utc(value, "backtest time")
        if value < self._current:
            raise ValueError("backtest clock cannot move backward")
        self._current = value
