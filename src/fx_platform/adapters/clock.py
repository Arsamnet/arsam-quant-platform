"""System and deterministic UTC clock adapters."""

from dataclasses import dataclass
from datetime import UTC, datetime

from fx_platform.domain.common import require_utc


class SystemClock:
    """Return an aware UTC system time."""

    def now(self) -> datetime:
        """Read the system clock in UTC."""
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class FixedClock:
    """Return one injected UTC instant without consulting the wall clock."""

    current: datetime

    def __post_init__(self) -> None:
        require_utc(self.current, "current")

    def now(self) -> datetime:
        """Return the configured instant."""
        return self.current
