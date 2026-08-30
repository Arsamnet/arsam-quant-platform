"""Broker-independent symbol metadata used by deterministic risk policy."""

from dataclasses import dataclass
from decimal import Decimal

from fx_platform.domain.common import require_positive_decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class SymbolSpecification:
    """Risk-relevant contract facts without an MT5 or broker dependency.

    ``tick_value`` is the monetary value, in ``tick_value_currency``, of one
    ``tick_size`` price movement for one whole lot.
    """

    symbol: str
    base_currency: str
    quote_currency: str
    contract_size: Decimal
    tick_size: Decimal
    tick_value: Decimal
    tick_value_currency: str
    volume_min: Decimal
    volume_max: Decimal
    volume_step: Decimal
    price_digits: int
    max_spread_ticks: int | None

    def __post_init__(self) -> None:
        for field_name, text_value in (
            ("symbol", self.symbol),
            ("base_currency", self.base_currency),
            ("quote_currency", self.quote_currency),
            ("tick_value_currency", self.tick_value_currency),
        ):
            if not text_value or text_value != text_value.upper():
                raise ValueError(f"{field_name} must be non-empty uppercase text")
        for field_name, decimal_value in (
            ("contract_size", self.contract_size),
            ("tick_size", self.tick_size),
            ("tick_value", self.tick_value),
            ("volume_min", self.volume_min),
            ("volume_max", self.volume_max),
            ("volume_step", self.volume_step),
        ):
            require_positive_decimal(decimal_value, field_name)
        if self.volume_max < self.volume_min:
            raise ValueError("volume_max must be greater than or equal to volume_min")
        if self.price_digits < 0:
            raise ValueError("price_digits must not be negative")
        if self.max_spread_ticks is not None and self.max_spread_ticks < 0:
            raise ValueError("max_spread_ticks must not be negative")

    @property
    def maximum_spread(self) -> Decimal | None:
        """Return the exact price-distance limit derived from ticks."""
        if self.max_spread_ticks is None:
            return None
        return self.tick_size * self.max_spread_ticks

    def accepts_volume(self, volume: Decimal) -> bool:
        """Return whether volume is within the broker-independent lot grid."""
        if volume < self.volume_min or volume > self.volume_max:
            return False
        return (volume - self.volume_min) % self.volume_step == Decimal(0)
