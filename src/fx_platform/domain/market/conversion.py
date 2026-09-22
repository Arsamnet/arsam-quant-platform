"""Explicit point-in-time currency conversion inputs and deterministic conversion."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, DecimalException
from enum import StrEnum

from fx_platform.domain.common import require_finite_decimal, require_positive_decimal, require_utc

_CURRENCY_CODE_LENGTH = 3


def _require_currency_code(value: str, field_name: str) -> None:
    if (
        len(value) != _CURRENCY_CODE_LENGTH
        or not value.isascii()
        or not value.isalpha()
        or value != value.upper()
    ):
        raise ValueError(f"{field_name} must be an uppercase ISO-style currency code")


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
            _require_currency_code(value, field_name)
        if self.source_currency == self.target_currency:
            raise ValueError("conversion currencies must be different")


@dataclass(frozen=True, slots=True, kw_only=True)
class BrokerFxQuote:
    """Caller-supplied exact broker pair Bid/Ask observation."""

    source_symbol: str
    base_currency: str
    quote_currency: str
    bid: Decimal
    ask: Decimal
    observed_at: datetime

    def __post_init__(self) -> None:
        require_utc(self.observed_at, "observed_at")
        require_positive_decimal(self.bid, "bid")
        require_positive_decimal(self.ask, "ask")
        _require_currency_code(self.base_currency, "base_currency")
        _require_currency_code(self.quote_currency, "quote_currency")
        if self.base_currency == self.quote_currency:
            raise ValueError("broker pair currencies must be different")
        if self.source_symbol != f"{self.base_currency}{self.quote_currency}":
            raise ValueError("source_symbol must exactly match broker pair currencies")
        if self.ask < self.bid:
            raise ValueError("ask must be greater than or equal to bid")


class CurrencyConversionDerivationMethod(StrEnum):
    """Reviewed ways a directed currency conversion may be derived."""

    INVERSE_EXACT_PAIR = "inverse_exact_pair"


class BrokerPriceSide(StrEnum):
    """Broker quote side used by a reviewed conversion derivation."""

    ASK = "ask"


@dataclass(frozen=True, slots=True, kw_only=True)
class InverseConversionRateDerivation:
    """Auditable result of deriving one directed rate from its exact reverse pair."""

    requested_source_currency: str
    requested_target_currency: str
    broker_quote: BrokerFxQuote
    derivation_method: CurrencyConversionDerivationMethod
    price_side: BrokerPriceSide
    conversion_rate: CurrencyConversionRate

    def __post_init__(self) -> None:
        _require_currency_code(self.requested_source_currency, "requested_source_currency")
        _require_currency_code(self.requested_target_currency, "requested_target_currency")
        if self.requested_source_currency == self.requested_target_currency:
            raise ValueError("conversion currencies must be different")
        if (
            self.broker_quote.base_currency != self.requested_target_currency
            or self.broker_quote.quote_currency != self.requested_source_currency
        ):
            raise ValueError("broker quote must be the exact inverse of the requested conversion")
        if self.derivation_method is not CurrencyConversionDerivationMethod.INVERSE_EXACT_PAIR:
            raise ValueError("unsupported currency conversion derivation method")
        if self.price_side is not BrokerPriceSide.ASK:
            raise ValueError("inverse exact-pair conversion must use the broker Ask")
        try:
            expected_rate = Decimal(1) / self.broker_quote.ask
        except DecimalException as error:
            raise ValueError("inverse conversion rate could not be derived") from error
        if (
            self.conversion_rate.source_currency != self.requested_source_currency
            or self.conversion_rate.target_currency != self.requested_target_currency
            or self.conversion_rate.observed_at != self.broker_quote.observed_at
            or self.conversion_rate.rate != expected_rate
        ):
            raise ValueError("derived conversion rate does not match inverse quote provenance")


def derive_inverse_conversion_rate(
    *,
    source_currency: str,
    target_currency: str,
    broker_quote: BrokerFxQuote,
) -> InverseConversionRateDerivation:
    """Derive ``source -> target`` only from the explicitly supplied exact reverse pair Ask."""
    _require_currency_code(source_currency, "source_currency")
    _require_currency_code(target_currency, "target_currency")
    if source_currency == target_currency:
        raise ValueError("conversion currencies must be different")
    if (
        broker_quote.base_currency != target_currency
        or broker_quote.quote_currency != source_currency
    ):
        raise ValueError("broker quote must be the exact inverse of the requested conversion")
    try:
        rate = Decimal(1) / broker_quote.ask
    except DecimalException as error:
        raise ValueError("inverse conversion rate could not be derived") from error
    require_positive_decimal(rate, "derived conversion rate")
    conversion_rate = CurrencyConversionRate(
        source_currency=source_currency,
        target_currency=target_currency,
        rate=rate,
        observed_at=broker_quote.observed_at,
    )
    return InverseConversionRateDerivation(
        requested_source_currency=source_currency,
        requested_target_currency=target_currency,
        broker_quote=broker_quote,
        derivation_method=CurrencyConversionDerivationMethod.INVERSE_EXACT_PAIR,
        price_side=BrokerPriceSide.ASK,
        conversion_rate=conversion_rate,
    )


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
