"""Static bootstrap market metadata adapters."""

from fx_platform.adapters.market.static import (
    StaticSymbolSpecificationProvider,
    bootstrap_symbol_specifications,
)

__all__ = ["StaticSymbolSpecificationProvider", "bootstrap_symbol_specifications"]
