"""Behavior tests for the illustrative deterministic strategy."""

from decimal import Decimal

import pytest

from fx_platform.domain.common import TradeSide
from fx_platform.domain.strategy import PreviousCloseMomentumStrategy
from tests.helpers import NOW, SIGNAL_ID, make_market, make_specification


def test_strategy_creates_buy_with_exact_stop_and_target() -> None:
    decision = PreviousCloseMomentumStrategy().evaluate(
        make_market(), make_specification(), signal_id=SIGNAL_ID, evaluated_at=NOW
    )

    assert decision.candidate is not None
    assert decision.candidate.side is TradeSide.BUY
    assert decision.candidate.entry_price == Decimal("1.1002")
    assert decision.candidate.stop_loss == Decimal("1.0992")
    assert decision.candidate.take_profit == Decimal("1.1022")
    assert decision.reasons == ("midpoint_above_previous_close",)


def test_strategy_creates_sell_from_lower_midpoint() -> None:
    market = make_market(
        bid=Decimal("1.0990"),
        ask=Decimal("1.0992"),
        previous_close=Decimal("1.1000"),
    )

    decision = PreviousCloseMomentumStrategy().evaluate(
        market, make_specification(), signal_id=SIGNAL_ID, evaluated_at=NOW
    )

    assert decision.candidate is not None
    assert decision.candidate.side is TradeSide.SELL
    assert decision.candidate.entry_price == Decimal("1.0990")
    assert decision.candidate.stop_loss == Decimal("1.1000")
    assert decision.candidate.take_profit == Decimal("1.0970")


def test_strategy_returns_explicit_no_signal_at_equal_midpoint() -> None:
    market = make_market(previous_close=Decimal("1.1001"))

    decision = PreviousCloseMomentumStrategy().evaluate(
        market, make_specification(), signal_id=SIGNAL_ID, evaluated_at=NOW
    )

    assert decision.candidate is None
    assert decision.reasons == ("midpoint_equals_previous_close",)


@pytest.mark.parametrize("field", ["volume", "stop_distance_ticks", "reward_to_risk"])
def test_strategy_rejects_non_positive_configuration(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        PreviousCloseMomentumStrategy(**{field: Decimal(0)})


@pytest.mark.parametrize(
    ("symbol", "base_currency"),
    (("EURUSD", "EUR"), ("GBPUSD", "GBP")),
)
def test_strategy_preserves_one_thousandth_stop_for_five_digit_symbols(
    symbol: str,
    base_currency: str,
) -> None:
    market = make_market(symbol=symbol)
    specification = make_specification(symbol=symbol, base_currency=base_currency)

    decision = PreviousCloseMomentumStrategy().evaluate(
        market,
        specification,
        signal_id=SIGNAL_ID,
        evaluated_at=NOW,
    )

    assert decision.candidate is not None
    assert decision.candidate.entry_price - decision.candidate.stop_loss == Decimal("0.00100")


def test_strategy_scales_usdjpy_stop_and_target_to_reviewed_ticks() -> None:
    market = make_market(
        symbol="USDJPY",
        bid=Decimal("157.319"),
        ask=Decimal("157.328"),
        previous_close=Decimal("157.658"),
    )
    specification = make_specification(
        symbol="USDJPY",
        base_currency="USD",
        quote_currency="JPY",
        tick_size=Decimal("0.001"),
        tick_value=Decimal(100),
        tick_value_currency="JPY",
    )

    decision = PreviousCloseMomentumStrategy().evaluate(
        market,
        specification,
        signal_id=SIGNAL_ID,
        evaluated_at=NOW,
    )

    assert decision.candidate is not None
    assert decision.candidate.side is TradeSide.SELL
    assert decision.candidate.stop_loss - decision.candidate.entry_price == Decimal("0.100")
    assert decision.candidate.entry_price - decision.candidate.take_profit == Decimal("0.200")
    assert decision.candidate.stop_loss == Decimal("157.419")
    assert decision.candidate.take_profit == Decimal("157.119")


def test_strategy_fails_closed_on_market_specification_symbol_mismatch() -> None:
    with pytest.raises(ValueError, match="does not match market symbol"):
        PreviousCloseMomentumStrategy().evaluate(
            make_market(symbol="EURUSD"),
            make_specification(symbol="GBPUSD", base_currency="GBP"),
            signal_id=SIGNAL_ID,
            evaluated_at=NOW,
        )


def test_strategy_remains_deterministic_for_identical_inputs() -> None:
    strategy = PreviousCloseMomentumStrategy()
    market = make_market()
    specification = make_specification()

    assert strategy.version == "1.1.0"

    first = strategy.evaluate(
        market,
        specification,
        signal_id=SIGNAL_ID,
        evaluated_at=NOW,
    )
    second = strategy.evaluate(
        market,
        specification,
        signal_id=SIGNAL_ID,
        evaluated_at=NOW,
    )

    assert first == second
    assert first.candidate is not None
    assert first.candidate.signal_id == SIGNAL_ID
