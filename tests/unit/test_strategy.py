"""Behavior tests for the illustrative deterministic strategy."""

from decimal import Decimal

import pytest

from fx_platform.domain.common import TradeSide
from fx_platform.domain.strategy import PreviousCloseMomentumStrategy
from tests.helpers import NOW, SIGNAL_ID, make_market


def test_strategy_creates_buy_with_exact_stop_and_target() -> None:
    decision = PreviousCloseMomentumStrategy().evaluate(
        make_market(), signal_id=SIGNAL_ID, evaluated_at=NOW
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
        market, signal_id=SIGNAL_ID, evaluated_at=NOW
    )

    assert decision.candidate is not None
    assert decision.candidate.side is TradeSide.SELL
    assert decision.candidate.entry_price == Decimal("1.0990")
    assert decision.candidate.stop_loss == Decimal("1.1000")
    assert decision.candidate.take_profit == Decimal("1.0970")


def test_strategy_returns_explicit_no_signal_at_equal_midpoint() -> None:
    market = make_market(previous_close=Decimal("1.1001"))

    decision = PreviousCloseMomentumStrategy().evaluate(
        market, signal_id=SIGNAL_ID, evaluated_at=NOW
    )

    assert decision.candidate is None
    assert decision.reasons == ("midpoint_equals_previous_close",)


@pytest.mark.parametrize("field", ["volume", "stop_distance", "reward_to_risk"])
def test_strategy_rejects_non_positive_configuration(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        PreviousCloseMomentumStrategy(**{field: Decimal(0)})
