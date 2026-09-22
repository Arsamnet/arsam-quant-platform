"""Audited exact-inverse currency conversion derivation tests."""

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone
from decimal import Decimal

import pytest

from fx_platform.domain.market import (
    BrokerFxQuote,
    BrokerPriceSide,
    CurrencyConversionDerivationMethod,
    InverseConversionRateDerivation,
    derive_inverse_conversion_rate,
)
from tests.helpers import NOW, make_inverse_conversion_derivation


def test_exact_inverse_derivation_uses_usdjpy_ask_and_retains_provenance() -> None:
    derivation = make_inverse_conversion_derivation()

    assert derivation.requested_source_currency == "JPY"
    assert derivation.requested_target_currency == "USD"
    assert derivation.broker_quote.source_symbol == "USDJPY"
    assert derivation.broker_quote.base_currency == "USD"
    assert derivation.broker_quote.quote_currency == "JPY"
    assert derivation.broker_quote.bid == Decimal("157.202")
    assert derivation.broker_quote.ask == Decimal("157.213")
    assert derivation.broker_quote.observed_at == NOW
    assert derivation.derivation_method is CurrencyConversionDerivationMethod.INVERSE_EXACT_PAIR
    assert derivation.price_side is BrokerPriceSide.ASK
    assert derivation.conversion_rate.source_currency == "JPY"
    assert derivation.conversion_rate.target_currency == "USD"
    assert derivation.conversion_rate.observed_at == NOW
    assert derivation.conversion_rate.rate == Decimal(1) / Decimal("157.213")
    assert derivation.conversion_rate.rate != Decimal(1) / Decimal("157.202")


def test_inverse_quote_and_derivation_are_immutable() -> None:
    derivation = make_inverse_conversion_derivation()

    with pytest.raises(FrozenInstanceError):
        derivation.price_side = BrokerPriceSide.ASK
    with pytest.raises(FrozenInstanceError):
        derivation.broker_quote.ask = Decimal(1)


@pytest.mark.parametrize(
    "changes",
    [
        {"source_symbol": "EURJPY"},
        {"base_currency": "usd"},
        {"quote_currency": "JP1"},
        {"base_currency": "USD", "quote_currency": "USD", "source_symbol": "USDUSD"},
        {"bid": Decimal(0)},
        {"bid": Decimal(-1)},
        {"ask": Decimal(0)},
        {"ask": Decimal(-1)},
        {"bid": Decimal("157.214")},
        {"observed_at": NOW.replace(tzinfo=None)},
        {"observed_at": NOW.astimezone(timezone(timedelta(hours=1)))},
    ],
)
def test_broker_fx_quote_rejects_invalid_or_inconsistent_facts(
    changes: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "source_symbol": "USDJPY",
        "base_currency": "USD",
        "quote_currency": "JPY",
        "bid": Decimal("157.202"),
        "ask": Decimal("157.213"),
        "observed_at": NOW,
    }
    values.update(changes)

    with pytest.raises(ValueError):
        BrokerFxQuote(**values)


@pytest.mark.parametrize(
    ("source_currency", "target_currency"),
    [
        ("EUR", "USD"),
        ("JPY", "EUR"),
        ("USD", "USD"),
        ("jpy", "USD"),
        ("JP1", "USD"),
    ],
)
def test_derivation_rejects_non_inverse_identity_or_malformed_requests(
    source_currency: str,
    target_currency: str,
) -> None:
    quote = make_inverse_conversion_derivation().broker_quote

    with pytest.raises(ValueError):
        derive_inverse_conversion_rate(
            source_currency=source_currency,
            target_currency=target_currency,
            broker_quote=quote,
        )


def test_derivation_rejects_a_rate_that_does_not_match_its_quote_provenance() -> None:
    derivation = make_inverse_conversion_derivation()

    with pytest.raises(ValueError, match="provenance"):
        replace(
            derivation,
            conversion_rate=replace(
                derivation.conversion_rate,
                rate=derivation.conversion_rate.rate + Decimal("0.000001"),
            ),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"requested_source_currency": "USD", "requested_target_currency": "USD"},
        {"requested_target_currency": "EUR"},
        {"derivation_method": "unsupported"},
        {"price_side": "bid"},
    ],
)
def test_derivation_value_rejects_unreviewed_or_inconsistent_construction(
    changes: dict[str, object],
) -> None:
    derivation = make_inverse_conversion_derivation()
    values: dict[str, object] = {
        "requested_source_currency": derivation.requested_source_currency,
        "requested_target_currency": derivation.requested_target_currency,
        "broker_quote": derivation.broker_quote,
        "derivation_method": derivation.derivation_method,
        "price_side": derivation.price_side,
        "conversion_rate": derivation.conversion_rate,
    }
    values.update(changes)

    with pytest.raises(ValueError):
        InverseConversionRateDerivation(**values)


@pytest.mark.parametrize(
    ("bid", "ask"),
    [
        (Decimal(1), Decimal("1e999999999")),
        (Decimal("1e-1000000000"), Decimal("1e-999999999")),
    ],
)
def test_non_positive_or_overflowing_inverse_result_rejects_fail_closed(
    bid: Decimal,
    ask: Decimal,
) -> None:
    quote = BrokerFxQuote(
        source_symbol="USDJPY",
        base_currency="USD",
        quote_currency="JPY",
        bid=bid,
        ask=ask,
        observed_at=NOW,
    )

    with pytest.raises(ValueError):
        derive_inverse_conversion_rate(
            source_currency="JPY",
            target_currency="USD",
            broker_quote=quote,
        )
