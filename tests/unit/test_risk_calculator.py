"""Hand-verifiable account-currency exposure calculation tests."""

from datetime import timedelta
from decimal import Decimal

from fx_platform.domain.risk import AccountCurrencyRiskCalculator, RiskCalculationFailure
from tests.helpers import (
    NOW,
    make_conversion_rate,
    make_inverse_conversion_derivation,
    make_signal,
    make_specification,
)


def _calculate(*, signal, specification, conversion_rates=()):
    return AccountCurrencyRiskCalculator().calculate(
        signal=signal,
        specification=specification,
        account_currency="USD",
        conversion_rates=conversion_rates,
        evaluated_at=NOW,
        max_conversion_age=timedelta(seconds=30),
        max_future_skew=timedelta(seconds=2),
    )


def test_eurusd_risk_for_usd_account_uses_usd_tick_value() -> None:
    result = _calculate(
        signal=make_signal(
            entry_price=Decimal("1.10000"),
            stop_loss=Decimal("1.09900"),
            volume=Decimal("0.01"),
        ),
        specification=make_specification(),
    )

    assert result is not None
    assert result.failure is None
    assert result.amount == Decimal(1)  # 100 ticks * USD 1/tick/lot * 0.01 lot


def test_gbpusd_risk_for_usd_account_is_directly_hand_verifiable() -> None:
    result = _calculate(
        signal=make_signal(
            symbol="GBPUSD",
            entry_price=Decimal("1.25000"),
            stop_loss=Decimal("1.24800"),
            volume=Decimal("0.02"),
        ),
        specification=make_specification(
            symbol="GBPUSD",
            base_currency="GBP",
            quote_currency="USD",
        ),
    )

    assert result is not None
    assert result.failure is None
    assert result.amount == Decimal(4)  # 200 ticks * USD 1/tick/lot * 0.02 lot


def test_usdjpy_risk_for_usd_account_requires_explicit_directed_rate() -> None:
    result = _calculate(
        signal=make_signal(
            symbol="USDJPY",
            entry_price=Decimal("150.000"),
            stop_loss=Decimal("149.900"),
            volume=Decimal("0.01"),
        ),
        specification=make_specification(
            symbol="USDJPY",
            base_currency="USD",
            quote_currency="JPY",
            tick_size=Decimal("0.001"),
            tick_value=Decimal(100),
            tick_value_currency="JPY",
        ),
        conversion_rates=(make_conversion_rate(rate=Decimal("0.0067")),),
    )

    assert result is not None
    assert result.failure is None
    assert result.amount == Decimal("0.6700")  # JPY 100 exposure * 0.0067 USD/JPY


def test_usdjpy_risk_accepts_directed_rate_from_audited_exact_inverse_derivation() -> None:
    derivation = make_inverse_conversion_derivation()
    result = _calculate(
        signal=make_signal(
            symbol="USDJPY",
            entry_price=Decimal("157.213"),
            stop_loss=Decimal("157.113"),
            volume=Decimal("0.01"),
        ),
        specification=make_specification(
            symbol="USDJPY",
            base_currency="USD",
            quote_currency="JPY",
            tick_size=Decimal("0.001"),
            tick_value=Decimal(100),
            tick_value_currency="JPY",
        ),
        conversion_rates=(derivation.conversion_rate,),
    )

    assert result is not None
    assert result.failure is None
    assert result.amount == Decimal(100) * (Decimal(1) / Decimal("157.213"))


def test_required_conversion_unavailable_fails_closed() -> None:
    result = _calculate(
        signal=make_signal(symbol="USDJPY"),
        specification=make_specification(
            symbol="USDJPY",
            base_currency="USD",
            quote_currency="JPY",
            tick_size=Decimal("0.001"),
            tick_value=Decimal(100),
            tick_value_currency="JPY",
        ),
    )

    assert result is not None
    assert result.amount is None
    assert result.failure is RiskCalculationFailure.CONVERSION_RATE_UNAVAILABLE


def test_zero_cross_currency_exposure_remains_exact_without_conversion_crash() -> None:
    result = _calculate(
        signal=make_signal(
            symbol="USDJPY",
            entry_price=Decimal("150.000"),
            stop_loss=Decimal("150.000"),
        ),
        specification=make_specification(
            symbol="USDJPY",
            base_currency="USD",
            quote_currency="JPY",
            tick_size=Decimal("0.001"),
            tick_value=Decimal(100),
            tick_value_currency="JPY",
        ),
        conversion_rates=(make_conversion_rate(),),
    )

    assert result is not None
    assert result.amount == Decimal(0)


def test_stale_future_and_ambiguous_conversion_inputs_fail_closed() -> None:
    signal = make_signal(symbol="USDJPY")
    specification = make_specification(
        symbol="USDJPY",
        base_currency="USD",
        quote_currency="JPY",
        tick_size=Decimal("0.001"),
        tick_value=Decimal(100),
        tick_value_currency="JPY",
    )
    stale = _calculate(
        signal=signal,
        specification=specification,
        conversion_rates=(make_conversion_rate(observed_at=NOW - timedelta(seconds=31)),),
    )
    future = _calculate(
        signal=signal,
        specification=specification,
        conversion_rates=(make_conversion_rate(observed_at=NOW + timedelta(seconds=3)),),
    )
    rate = make_conversion_rate()
    ambiguous = _calculate(
        signal=signal,
        specification=specification,
        conversion_rates=(rate, rate),
    )

    assert stale is not None
    assert stale.failure is RiskCalculationFailure.CONVERSION_RATE_STALE
    assert future is not None
    assert future.failure is RiskCalculationFailure.CONVERSION_RATE_IN_FUTURE
    assert ambiguous is not None
    assert ambiguous.failure is RiskCalculationFailure.CONVERSION_RATE_AMBIGUOUS
