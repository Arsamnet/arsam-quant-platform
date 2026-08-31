"""Explicit point-in-time currency conversion inputs and deterministic conversion."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from fx_platform.domain.common import require_finite_decimal, require_positive_decimal, require_utc

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


class CurrencyConversionFailure(StrEnum):
    """Fail-closed causes shared by risk and portfolio accounting."""

    CONVERSION_RATE_UNAVAILABLE = "conversion_rate_unavailable"
    CONVERSION_RATE_AMBIGUOUS = "conversion_rate_ambiguous"
    CONVERSION_RATE_STALE = "conversion_rate_stale"
    CONVERSION_RATE_IN_FUTURE = "conversion_rate_in_future"


@dataclass(frozen=True, slots=True, kw_only=True)
class CurrencyConversionResult:
    """Either an exact converted amount or one explicit failure."""

    amount: Decimal | None
    failure: CurrencyConversionFailure | None

    def __post_init__(self) -> None:
        if (self.amount is None) == (self.failure is None):
            raise ValueError("currency conversion must contain exactly one result")


def convert_currency(
    *,
    amount: Decimal,
    source_currency: str,
    target_currency: str,
    conversion_rates: tuple[CurrencyConversionRate, ...],
    evaluated_at: datetime,
    max_conversion_age: timedelta,
    max_future_skew: timedelta,
) -> CurrencyConversionResult:
    """Convert with exactly one fresh directed rate; identity conversion is exact."""
    require_utc(evaluated_at, "evaluated_at")
    require_finite_decimal(amount, "amount")
    if amount < Decimal(0):
        raise ValueError("amount must not be negative")
    if source_currency == target_currency:
        return CurrencyConversionResult(amount=amount, failure=None)

    matching_rates = tuple(
        rate
        for rate in conversion_rates
        if rate.source_currency == source_currency and rate.target_currency == target_currency
    )
    if not matching_rates:
        return CurrencyConversionResult(
            amount=None,
            failure=CurrencyConversionFailure.CONVERSION_RATE_UNAVAILABLE,
        )
    if len(matching_rates) > 1:
        return CurrencyConversionResult(
            amount=None,
            failure=CurrencyConversionFailure.CONVERSION_RATE_AMBIGUOUS,
        )

    rate = matching_rates[0]
    if rate.observed_at - evaluated_at > max_future_skew:
        return CurrencyConversionResult(
            amount=None,
            failure=CurrencyConversionFailure.CONVERSION_RATE_IN_FUTURE,
        )
    if evaluated_at - rate.observed_at > max_conversion_age:
        return CurrencyConversionResult(
            amount=None,
            failure=CurrencyConversionFailure.CONVERSION_RATE_STALE,
        )
    return CurrencyConversionResult(amount=amount * rate.rate, failure=None)
