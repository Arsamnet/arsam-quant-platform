"""Regression coverage for broker-calibrated inverse stop-loss conversion."""

from decimal import Decimal

from fx_platform.domain.market import BrokerPriceSide
from tests.helpers import make_inverse_conversion_derivation


def test_fibogroup_usdjpy_loss_side_calibration_drives_stop_exposure() -> None:
    bid = Decimal("157.776")
    ask = Decimal("157.786")
    observed_tick_value_profit = Decimal("0.6337697894616760")
    observed_tick_value_loss = Decimal("0.6338099584220667")
    one_tick_jpy_exposure = Decimal(100)

    derivation = make_inverse_conversion_derivation(bid=bid, ask=ask)
    risk_tick_value = one_tick_jpy_exposure / bid
    profit_tick_value = one_tick_jpy_exposure / ask

    assert derivation.price_side is BrokerPriceSide.BID
    assert derivation.conversion_rate.rate == Decimal(1) / bid
    assert risk_tick_value.quantize(Decimal("0.0000000000000001")) == observed_tick_value_loss
    assert abs(profit_tick_value - observed_tick_value_profit) <= Decimal("1e-16")
    assert derivation.conversion_rate.rate != Decimal(1) / ask
    assert risk_tick_value != profit_tick_value
