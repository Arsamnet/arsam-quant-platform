"""Regression protection against wall-clock and result-identity drift."""

from decimal import Decimal

from tests.backtesting_helpers import make_backtest_engine, sample_dataset


def test_identical_inputs_have_identical_run_trade_and_canonical_result_ids() -> None:
    dataset = sample_dataset()
    first = make_backtest_engine().run(dataset, starting_balance=Decimal(10000))
    second = make_backtest_engine().run(dataset, starting_balance=Decimal(10000))

    assert first.metadata.run_id == second.metadata.run_id
    assert tuple(trade.trade_id for trade in first.trades) == tuple(
        trade.trade_id for trade in second.trades
    )
    assert first.to_json().encode() == second.to_json().encode()
