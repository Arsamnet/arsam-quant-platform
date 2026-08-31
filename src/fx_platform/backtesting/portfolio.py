"""Minimal explicit simulated portfolio accounting and realized metrics."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fx_platform.backtesting.models import BacktestReport, SimulatedPosition, TradeRecord
from fx_platform.domain.common import require_positive_decimal, require_utc

_CURRENCY_CODE_LENGTH = 3


class SimulatedPortfolio:
    """Own position and balance transitions without global mutable state."""

    def __init__(self, *, initial_balance: Decimal, account_currency: str) -> None:
        require_positive_decimal(initial_balance, "initial_balance")
        if (
            len(account_currency) != _CURRENCY_CODE_LENGTH
            or account_currency != account_currency.upper()
        ):
            raise ValueError("account_currency must be an uppercase ISO-style code")
        self._initial_balance = initial_balance
        self._account_currency = account_currency
        self._balance = initial_balance
        self._equity = initial_balance
        self._peak_balance = initial_balance
        self._maximum_drawdown = Decimal(0)
        self._positions: dict[UUID, SimulatedPosition] = {}
        self._closed_trades: list[TradeRecord] = []
        self._daily_realized: dict[date, Decimal] = {}
        self._transaction_costs = Decimal(0)

    @property
    def initial_balance(self) -> Decimal:
        return self._initial_balance

    @property
    def account_currency(self) -> str:
        return self._account_currency

    @property
    def balance(self) -> Decimal:
        return self._balance

    @property
    def equity(self) -> Decimal:
        return self._equity

    @property
    def open_positions(self) -> tuple[SimulatedPosition, ...]:
        return tuple(self._positions.values())

    @property
    def closed_trades(self) -> tuple[TradeRecord, ...]:
        return tuple(self._closed_trades)

    @property
    def realized_pnl(self) -> Decimal:
        return self._balance - self._initial_balance

    @property
    def transaction_costs(self) -> Decimal:
        return self._transaction_costs

    @property
    def maximum_drawdown(self) -> Decimal:
        return self._maximum_drawdown

    def daily_realized_pnl(self, value: datetime) -> Decimal:
        """Return realized P/L allocated to the logical UTC date."""
        require_utc(value, "portfolio timestamp")
        return self._daily_realized.get(value.date(), Decimal(0))

    def open(self, position: SimulatedPosition) -> None:
        """Record entry commission immediately and add one unique position."""
        if position.position_id in self._positions:
            raise ValueError("position already exists")
        self._positions[position.position_id] = position
        self._balance -= position.entry_commission
        self._daily_realized[position.opened_at.date()] = (
            self._daily_realized.get(position.opened_at.date(), Decimal(0))
            - position.entry_commission
        )
        self._transaction_costs += (
            position.entry_commission + position.entry_spread_cost + position.entry_slippage_cost
        )
        self._update_balance_drawdown()

    def close(self, trade: TradeRecord) -> None:
        """Close one matching position and realize the exact ledger result once."""
        position = self._positions.get(trade.position_id)
        if position is None:
            raise ValueError("closed trade does not match an open position")
        if position.execution_id != trade.execution_id:
            raise ValueError("trade execution does not match its position")
        del self._positions[trade.position_id]
        close_balance_change = trade.net_pnl + position.entry_commission
        self._balance += close_balance_change
        self._daily_realized[trade.closed_at.date()] = (
            self._daily_realized.get(trade.closed_at.date(), Decimal(0)) + close_balance_change
        )
        self._transaction_costs += (
            trade.spread_cost
            + trade.commission
            + trade.slippage_cost
            + trade.swap_cost
            - position.entry_spread_cost
            - position.entry_commission
            - position.entry_slippage_cost
        )
        self._closed_trades.append(trade)
        self._update_balance_drawdown()

    def mark_to_market(self, unrealized_values: tuple[Decimal, ...]) -> None:
        """Set deterministic liquidation equity for the currently open positions."""
        if len(unrealized_values) != len(self._positions):
            raise ValueError("one unrealized value is required for every open position")
        self._equity = self._balance + sum(unrealized_values, start=Decimal(0))

    def report(self) -> BacktestReport:
        """Calculate closed-trade metrics with explicit undefined edge cases."""
        trades = self.closed_trades
        winners = tuple(trade for trade in trades if trade.net_pnl > Decimal(0))
        losers = tuple(trade for trade in trades if trade.net_pnl < Decimal(0))
        gross_profit = sum((trade.net_pnl for trade in winners), start=Decimal(0))
        gross_loss = abs(sum((trade.net_pnl for trade in losers), start=Decimal(0)))
        closed_trade_pnl = sum((trade.net_pnl for trade in trades), start=Decimal(0))
        count = len(trades)
        win_rate = None if count == 0 else Decimal(len(winners)) / Decimal(count)
        average_trade = None if count == 0 else closed_trade_pnl / Decimal(count)
        average_winner = None if not winners else gross_profit / Decimal(len(winners))
        average_loser = (
            None
            if not losers
            else sum((trade.net_pnl for trade in losers), start=Decimal(0)) / Decimal(len(losers))
        )
        profit_factor = None if gross_loss == Decimal(0) else gross_profit / gross_loss
        payoff_ratio = (
            None
            if average_winner is None or average_loser is None
            else average_winner / abs(average_loser)
        )
        return BacktestReport(
            initial_balance=self._initial_balance,
            final_balance=self._balance,
            final_equity=self._equity,
            net_pnl=self.realized_pnl,
            return_fraction=self.realized_pnl / self._initial_balance,
            return_percentage=self.realized_pnl / self._initial_balance * Decimal(100),
            trade_count=count,
            winning_trade_count=len(winners),
            losing_trade_count=len(losers),
            win_rate=win_rate,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=profit_factor,
            maximum_drawdown=self._maximum_drawdown,
            average_trade=average_trade,
            average_winner=average_winner,
            average_loser=average_loser,
            expectancy=average_trade,
            payoff_ratio=payoff_ratio,
            transaction_costs=self._transaction_costs,
            realized_pnl=self.realized_pnl,
            open_position_count=len(self._positions),
        )

    def _update_balance_drawdown(self) -> None:
        self._peak_balance = max(self._peak_balance, self._balance)
        self._maximum_drawdown = max(
            self._maximum_drawdown,
            self._peak_balance - self._balance,
        )
