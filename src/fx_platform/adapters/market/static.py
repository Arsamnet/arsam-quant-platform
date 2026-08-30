"""Reviewed static symbol metadata for the paper-only bootstrap."""

from collections.abc import Iterable
from decimal import Decimal

from fx_platform.domain.market import SymbolSpecification

_BOOTSTRAP_SPECIFICATIONS = {
    "EURUSD": SymbolSpecification(
        symbol="EURUSD",
        base_currency="EUR",
        quote_currency="USD",
        contract_size=Decimal(100000),
        tick_size=Decimal("0.00001"),
        tick_value=Decimal(1),
        tick_value_currency="USD",
        volume_min=Decimal("0.01"),
        volume_max=Decimal("0.10"),
        volume_step=Decimal("0.01"),
        price_digits=5,
        max_spread_ticks=50,
    ),
    "GBPUSD": SymbolSpecification(
        symbol="GBPUSD",
        base_currency="GBP",
        quote_currency="USD",
        contract_size=Decimal(100000),
        tick_size=Decimal("0.00001"),
        tick_value=Decimal(1),
        tick_value_currency="USD",
        volume_min=Decimal("0.01"),
        volume_max=Decimal("0.10"),
        volume_step=Decimal("0.01"),
        price_digits=5,
        max_spread_ticks=50,
    ),
    "USDJPY": SymbolSpecification(
        symbol="USDJPY",
        base_currency="USD",
        quote_currency="JPY",
        contract_size=Decimal(100000),
        tick_size=Decimal("0.001"),
        tick_value=Decimal(100),
        tick_value_currency="JPY",
        volume_min=Decimal("0.01"),
        volume_max=Decimal("0.10"),
        volume_step=Decimal("0.01"),
        price_digits=3,
        max_spread_ticks=50,
    ),
}


class StaticSymbolSpecificationProvider:
    """Read reviewed symbol facts from an immutable in-process mapping."""

    def __init__(self, specifications: Iterable[SymbolSpecification]) -> None:
        by_symbol = {specification.symbol: specification for specification in specifications}
        if not by_symbol:
            raise ValueError("at least one symbol specification is required")
        self._by_symbol = by_symbol

    def get(self, symbol: str) -> SymbolSpecification | None:
        """Return a configured specification or no value for early rejection."""
        return self._by_symbol.get(symbol)


def bootstrap_symbol_specifications(
    allowed_symbols: frozenset[str],
) -> StaticSymbolSpecificationProvider:
    """Select reviewed paper metadata and fail startup for unsupported symbols."""
    unsupported = allowed_symbols - _BOOTSTRAP_SPECIFICATIONS.keys()
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise ValueError(f"no reviewed bootstrap symbol specification for: {names}")
    return StaticSymbolSpecificationProvider(
        _BOOTSTRAP_SPECIFICATIONS[symbol] for symbol in sorted(allowed_symbols)
    )
