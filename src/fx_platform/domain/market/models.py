"""Immutable point-in-time market and account observations."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fx_platform.domain.common import (
    require_finite_decimal,
    require_positive_decimal,
    require_utc,
)

_CURRENCY_CODE_LENGTH = 3


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketSnapshot:
    """An immutable Bid/Ask observation available at a specific UTC instant."""

    snapshot_id: UUID
    symbol: str
    observed_at: datetime
    bid: Decimal
    ask: Decimal
    previous_close: Decimal

    def __post_init__(self) -> None:
        require_utc(self.observed_at, "observed_at")
        require_positive_decimal(self.bid, "bid")
        require_positive_decimal(self.ask, "ask")
        require_positive_decimal(self.previous_close, "previous_close")
        if not self.symbol or self.symbol != self.symbol.upper():
            raise ValueError("symbol must be non-empty uppercase text")
        if self.ask < self.bid:
            raise ValueError("ask must be greater than or equal to bid")

    @property
    def spread(self) -> Decimal:
        """Return the exact Bid/Ask spread."""
        return self.ask - self.bid

    @property
    def mid_price(self) -> Decimal:
        """Return the exact midpoint used by the example strategy."""
        return (self.ask + self.bid) / Decimal(2)


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountSnapshot:
    """Risk-relevant account state captured at a UTC instant."""

    account_id: str
    observed_at: datetime
    balance: Decimal
    equity: Decimal
    daily_realized_pnl: Decimal
    open_position_count: int
    currency: str = "USD"

    def __post_init__(self) -> None:
        require_utc(self.observed_at, "observed_at")
        require_positive_decimal(self.balance, "balance")
        require_finite_decimal(self.equity, "equity")
        require_finite_decimal(self.daily_realized_pnl, "daily_realized_pnl")
        if not self.account_id:
            raise ValueError("account_id must not be empty")
        if len(self.currency) != _CURRENCY_CODE_LENGTH or self.currency != self.currency.upper():
            raise ValueError("currency must be an uppercase ISO-style currency code")
        if self.equity < Decimal(0):
            raise ValueError("equity must not be negative")
        if self.open_position_count < 0:
            raise ValueError("open_position_count must not be negative")
