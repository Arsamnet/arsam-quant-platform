"""Bid/Ask fills, conservative exits, conversion, and portfolio accounting tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from fx_platform.backtesting.broker import BacktestExecutionError, SimulatedBroker
from fx_platform.backtesting.conversion import PointInTimeConversionBook
from fx_platform.backtesting.dataset import HistoricalBar
from fx_platform.backtesting.models import (
    ExecutionConfiguration,
    ExitReason,
    SimulatedPosition,
    TradeRecord,
)
from fx_platform.backtesting.portfolio import SimulatedPortfolio
from fx_platform.domain.common import TradeSide, TradingMode
from fx_platform.domain.execution import ExecutionIntent
from tests.helpers import make_conversion_rate, make_specification

NOW = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)


def _bar(**changes: object) -> HistoricalBar:
    values: dict[str, object] = {
        "symbol": "EURUSD",
        "timeframe": "M1",
        "opened_at": NOW,
        "bid_open": Decimal("1.1000"),
        "bid_high": Decimal("1.1010"),
        "bid_low": Decimal("1.0990"),
        "bid_close": Decimal("1.1000"),
        "spread": Decimal("0.0002"),
    }
    values.update(changes)
    return HistoricalBar(**values)


def _intent(*, side: TradeSide = TradeSide.BUY, **changes: object) -> ExecutionIntent:
    values: dict[str, object] = {
        "execution_id": uuid4(),
        "decision_id": uuid4(),
        "signal_id": uuid4(),
        "risk_decision_id": uuid4(),
        "created_at": NOW - timedelta(minutes=1),
        "expires_at": NOW + timedelta(minutes=5),
        "node_id": "deterministic-backtest",
        "symbol": "EURUSD",
        "side": side,
        "volume": Decimal("0.01"),
        "entry_price": Decimal("1.1002") if side is TradeSide.BUY else Decimal("1.1000"),
        "stop_loss": Decimal("1.0980") if side is TradeSide.BUY else Decimal("1.1020"),
        "take_profit": Decimal("1.1020") if side is TradeSide.BUY else Decimal("1.0980"),
        "trading_mode": TradingMode.PAPER,
    }
    values.update(changes)
    return ExecutionIntent(**values)


def _broker(**changes: object) -> SimulatedBroker:
    values: dict[str, object] = {
        "configuration": ExecutionConfiguration(),
        "account_currency": "USD",
        "max_conversion_age": timedelta(minutes=5),
    }
    values.update(changes)
    return SimulatedBroker(**values)


def test_broker_fills_buy_at_ask_sell_at_bid_and_suppresses_duplicate() -> None:
    broker = _broker()
    buy = _intent()
    sell = _intent(side=TradeSide.SELL)

    assert broker.submit(buy).accepted
    assert not broker.submit(buy).accepted
    assert broker.submit(sell).accepted
    assert broker.pending_intents == (buy, sell)
    positions = tuple(
        outcome.position
        for outcome in broker.fill_pending(
            bar=_bar(),
            specification=make_specification(),
            conversion_rates=(),
        )
        if outcome.position is not None
    )

    assert broker.pending_intents == ()
    assert positions[0].executed_entry_price == Decimal("1.10021")
    assert positions[1].executed_entry_price == Decimal("1.09999")
    assert positions[0].entry_spread_cost == Decimal("0.100000")
    assert positions[0].entry_slippage_cost == Decimal("0.0100000")
    assert broker.unrealized_pnl(
        position=positions[0],
        bar=_bar(),
        specification=make_specification(),
        conversion_rates=(),
    ) == Decimal("-0.2550000")
    assert broker.unrealized_pnl(
        position=positions[1],
        bar=_bar(),
        specification=make_specification(),
        conversion_rates=(),
    ) == Decimal("-0.2550000")


def test_sell_take_profit_uses_ask_and_explicit_cost_identity() -> None:
    broker = _broker()
    sell = _intent(side=TradeSide.SELL)
    broker.submit(sell)
    position = broker.fill_pending(
        bar=_bar(),
        specification=make_specification(),
        conversion_rates=(),
    )[0].position
    assert position is not None
    exit_bar = _bar(
        opened_at=NOW + timedelta(minutes=1),
        bid_open=Decimal("1.0990"),
        bid_high=Decimal("1.0995"),
        bid_low=Decimal("1.0975"),
        bid_close=Decimal("1.0980"),
    )

    trade = broker.exits_for_bar(
        bar=exit_bar,
        positions=(position,),
        specification=make_specification(),
        conversion_rates=(),
    )[0]

    assert trade.exit_reason is ExitReason.TAKE_PROFIT
    assert trade.exit_price == Decimal("1.09801")
    assert trade.gross_pnl == Decimal("2.200000")
    assert trade.net_pnl == Decimal("1.9100000")
    assert trade.net_pnl == (
        trade.gross_pnl - trade.spread_cost - trade.commission - trade.slippage_cost
    )


@pytest.mark.parametrize(
    ("intent_changes", "bar_changes", "spec_changes", "slippage_ticks", "reason"),
    [
        (
            {"created_at": NOW - timedelta(minutes=2), "expires_at": NOW - timedelta(minutes=1)},
            {},
            {},
            Decimal(1),
            "execution_intent_expired",
        ),
        ({}, {}, {"max_spread_ticks": None}, Decimal(1), "spread_policy_unavailable"),
        ({}, {"spread": Decimal("0.001")}, {}, Decimal(1), "spread_too_wide_at_fill"),
        (
            {"side": TradeSide.SELL},
            {
                "bid_open": Decimal("0.00001"),
                "bid_high": Decimal("0.00002"),
                "bid_low": Decimal("0.00001"),
                "bid_close": Decimal("0.00001"),
            },
            {},
            Decimal(2),
            "invalid_filled_entry",
        ),
        ({"stop_loss": Decimal("1.2")}, {}, {}, Decimal(1), "stop_invalid_at_fill"),
        ({"take_profit": Decimal("1.0")}, {}, {}, Decimal(1), "take_profit_invalid_at_fill"),
    ],
)
def test_fill_rejections_are_explicit_and_fail_closed(
    intent_changes: dict[str, object],
    bar_changes: dict[str, object],
    spec_changes: dict[str, object],
    slippage_ticks: Decimal,
    reason: str,
) -> None:
    broker = _broker(configuration=ExecutionConfiguration(slippage_ticks=slippage_ticks))
    intent = _intent(**intent_changes)
    broker.submit(intent)

    outcome = broker.fill_pending(
        bar=_bar(**bar_changes),
        specification=replace(make_specification(), **spec_changes),
        conversion_rates=(),
    )[0]

    assert outcome.position is None
    assert outcome.rejection_reason == reason


def test_nonmatching_symbol_and_untouched_positions_remain_open() -> None:
    broker = _broker()
    intent = _intent()
    broker.submit(intent)
    other_bar = _bar(
        symbol="GBPUSD",
        bid_open=Decimal("1.25"),
        bid_high=Decimal("1.26"),
        bid_low=Decimal("1.24"),
        bid_close=Decimal("1.25"),
    )
    assert (
        broker.fill_pending(
            bar=other_bar,
            specification=make_specification(symbol="GBPUSD", base_currency="GBP"),
            conversion_rates=(),
        )
        == ()
    )
    position = broker.fill_pending(
        bar=_bar(),
        specification=make_specification(),
        conversion_rates=(),
    )[0].position
    assert position is not None
    untouched = _bar(
        opened_at=NOW + timedelta(minutes=1),
        bid_high=Decimal("1.1010"),
        bid_low=Decimal("1.0995"),
    )
    assert (
        broker.exits_for_bar(
            bar=untouched,
            positions=(replace(position, symbol="GBPUSD"), position),
            specification=make_specification(),
            conversion_rates=(),
        )
        == ()
    )


def test_cross_currency_fill_requires_fresh_directed_conversion() -> None:
    specification = make_specification(
        symbol="USDJPY",
        base_currency="USD",
        quote_currency="JPY",
        tick_size=Decimal("0.001"),
        tick_value=Decimal(100),
        tick_value_currency="JPY",
    )
    broker = _broker()
    intent = _intent(
        symbol="USDJPY",
        entry_price=Decimal("150.010"),
        stop_loss=Decimal("149.900"),
        take_profit=Decimal("150.200"),
    )
    broker.submit(intent)
    bar = _bar(
        symbol="USDJPY",
        bid_open=Decimal("150.000"),
        bid_high=Decimal("150.100"),
        bid_low=Decimal("149.950"),
        bid_close=Decimal("150.000"),
        spread=Decimal("0.010"),
    )

    with pytest.raises(BacktestExecutionError, match="conversion_rate_unavailable"):
        broker.fill_pending(
            bar=bar,
            specification=specification,
            conversion_rates=(),
        )


def test_conversion_book_hides_future_and_selects_latest_known_rate() -> None:
    old = make_conversion_rate(observed_at=NOW - timedelta(minutes=1), rate=Decimal("0.006"))
    current = make_conversion_rate(observed_at=NOW, rate=Decimal("0.007"))
    future = make_conversion_rate(observed_at=NOW + timedelta(minutes=1), rate=Decimal("0.008"))
    book = PointInTimeConversionBook((future, old, current))

    assert book.available_at(NOW) == (current,)
    assert book.available_at(NOW - timedelta(seconds=30)) == (old,)
    with pytest.raises(ValueError, match="duplicate"):
        PointInTimeConversionBook((current, current))
    with pytest.raises(ValueError, match="UTC"):
        book.available_at(NOW.replace(tzinfo=None))


def _position(*, commission: Decimal = Decimal(0)) -> SimulatedPosition:
    return SimulatedPosition(
        position_id=uuid4(),
        execution_id=uuid4(),
        signal_id=uuid4(),
        risk_decision_id=uuid4(),
        symbol="EURUSD",
        side=TradeSide.BUY,
        volume=Decimal("0.01"),
        requested_entry_price=Decimal("1.1"),
        reference_entry_price=Decimal("1.1"),
        executed_entry_price=Decimal("1.1"),
        stop_loss=Decimal("1.0"),
        take_profit=Decimal("1.2"),
        opened_at=NOW,
        entry_spread_cost=Decimal(0),
        entry_commission=commission,
        entry_slippage_cost=Decimal(0),
    )


def _trade(position: SimulatedPosition, gross_pnl: Decimal) -> TradeRecord:
    return TradeRecord(
        trade_id=uuid4(),
        position_id=position.position_id,
        signal_id=position.signal_id,
        risk_decision_id=position.risk_decision_id,
        execution_id=position.execution_id,
        symbol=position.symbol,
        side=position.side,
        volume=position.volume,
        requested_entry_price=position.requested_entry_price,
        executed_entry_price=position.executed_entry_price,
        exit_price=Decimal("1.11"),
        stop_loss=position.stop_loss,
        take_profit=position.take_profit,
        opened_at=position.opened_at,
        closed_at=NOW + timedelta(minutes=1),
        exit_reason=ExitReason.TAKE_PROFIT,
        gross_pnl=gross_pnl,
        spread_cost=Decimal(0),
        commission=position.entry_commission,
        slippage_cost=Decimal(0),
        swap_cost=Decimal(0),
        net_pnl=gross_pnl - position.entry_commission,
    )


def test_portfolio_tracks_balance_drawdown_equity_and_hand_verifiable_metrics() -> None:
    portfolio = SimulatedPortfolio(initial_balance=Decimal(100), account_currency="USD")
    winner = _position()
    loser = _position()
    portfolio.open(winner)
    portfolio.close(_trade(winner, Decimal(10)))
    portfolio.open(loser)
    portfolio.mark_to_market((Decimal(-3),))
    assert portfolio.equity == Decimal(107)
    portfolio.close(_trade(loser, Decimal(-15)))

    report = portfolio.report()
    assert portfolio.initial_balance == Decimal(100)
    assert portfolio.account_currency == "USD"
    assert portfolio.balance == Decimal(95)
    assert portfolio.realized_pnl == Decimal(-5)
    assert portfolio.maximum_drawdown == Decimal(15)
    assert portfolio.transaction_costs == Decimal(0)
    assert portfolio.daily_realized_pnl(NOW) == Decimal(-5)
    assert report.gross_profit == Decimal(10)
    assert report.gross_loss == Decimal(15)
    assert report.profit_factor == Decimal(10) / Decimal(15)
    assert report.payoff_ratio == Decimal(10) / Decimal(15)
    assert report.average_trade == Decimal("-2.5")
    assert report.win_rate == Decimal("0.5")


def test_portfolio_zero_trade_metrics_and_invalid_transitions_are_explicit() -> None:
    portfolio = SimulatedPortfolio(initial_balance=Decimal(100), account_currency="USD")
    report = portfolio.report()
    assert report.profit_factor is None
    assert report.win_rate is None
    assert report.average_trade is None
    assert report.average_winner is None
    assert report.average_loser is None
    assert report.expectancy is None
    assert report.payoff_ratio is None

    position = _position(commission=Decimal(1))
    portfolio.open(position)
    assert portfolio.daily_realized_pnl(NOW) == Decimal(-1)
    with pytest.raises(ValueError, match="already"):
        portfolio.open(position)
    with pytest.raises(ValueError, match="one unrealized"):
        portfolio.mark_to_market(())
    with pytest.raises(ValueError, match="match"):
        portfolio.close(_trade(_position(), Decimal(1)))
    mismatched = replace(_trade(position, Decimal(1)), execution_id=uuid4())
    with pytest.raises(ValueError, match="execution"):
        portfolio.close(mismatched)

    with pytest.raises(ValueError):
        SimulatedPortfolio(initial_balance=Decimal(0), account_currency="USD")
    with pytest.raises(ValueError, match="account_currency"):
        SimulatedPortfolio(initial_balance=Decimal(1), account_currency="usd")
