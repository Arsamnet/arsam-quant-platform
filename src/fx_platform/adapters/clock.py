"""System UTC clock adapter."""

from datetime import UTC, datetime


class SystemClock:
    """Return an aware UTC system time."""

    def now(self) -> datetime:
        """Read the system clock in UTC."""
        return datetime.now(UTC)
