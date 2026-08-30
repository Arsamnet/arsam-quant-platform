"""Explicit point-in-time currency conversion inputs."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from fx_platform.domain.common import require_positive_decimal, require_utc

_CURRENCY_CODE_LENGTH = 3


@dataclass(frozen=True, slots=True, kw_only=True)
class CurrencyConversionRate:
    """A directed conversion rate supplied to the risk calculation boundary."""

    source_currency: str
    target_currency: str
    rate: Decimal
    observed_at: datetime

    def __post_init__(self) -> None:
        require_utc(self.observed_at, "observed_at")
        require_positive_decimal(self.rate, "rate")
        for field_name, value in (
            ("source_currency", self.source_currency),
            ("target_currency", self.target_currency),
        ):
            if len(value) != _CURRENCY_CODE_LENGTH or value != value.upper():
                raise ValueError(f"{field_name} must be an uppercase ISO-style currency code")
        if self.source_currency == self.target_currency:
            raise ValueError("conversion currencies must be different")
