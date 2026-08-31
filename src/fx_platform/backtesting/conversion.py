"""Point-in-time conversion replay that never exposes a future rate."""

from dataclasses import dataclass
from datetime import datetime

from fx_platform.domain.common import require_utc
from fx_platform.domain.market import CurrencyConversionRate


@dataclass(frozen=True, slots=True)
class PointInTimeConversionBook:
    """Select the latest known rate for each directed pair at a logical instant."""

    _rates: tuple[CurrencyConversionRate, ...] = ()

    def __post_init__(self) -> None:
        identities: set[tuple[str, str, datetime]] = set()
        for rate in self._rates:
            identity = (rate.source_currency, rate.target_currency, rate.observed_at)
            if identity in identities:
                raise ValueError("duplicate point-in-time currency conversion rate")
            identities.add(identity)

    def available_at(self, value: datetime) -> tuple[CurrencyConversionRate, ...]:
        """Return only latest observations whose timestamps are not in the future."""
        require_utc(value, "conversion lookup time")
        latest: dict[tuple[str, str], CurrencyConversionRate] = {}
        for rate in self._rates:
            if rate.observed_at > value:
                continue
            pair = (rate.source_currency, rate.target_currency)
            prior = latest.get(pair)
            if prior is None or rate.observed_at > prior.observed_at:
                latest[pair] = rate
        return tuple(latest[pair] for pair in sorted(latest))
