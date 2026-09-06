"""Fail-closed mapping from canonical broker metadata to domain symbol facts."""

from decimal import Decimal

from fx_platform.broker_validation.models import (
    BrokerSymbolSnapshot,
    CalculationMode,
    SymbolTradeMode,
)
from fx_platform.domain.market import SymbolSpecification


class SymbolSpecificationMappingError(ValueError):
    """Broker metadata cannot be represented safely by SymbolSpecification."""


class SymbolSpecificationMapper:
    """Map only the FX modes and symmetric tick-value semantics currently understood."""

    _SUPPORTED_CALCULATION_MODES = frozenset(
        {CalculationMode.FOREX, CalculationMode.FOREX_NO_LEVERAGE}
    )

    def map(
        self,
        snapshot: BrokerSymbolSnapshot,
        *,
        max_spread_ticks: int | None,
    ) -> SymbolSpecification:
        """Create an exact domain value or reject any unsupported required assumption."""
        if snapshot.trade_mode is not SymbolTradeMode.FULL:
            raise SymbolSpecificationMappingError("symbol is not fully trade-enabled")
        if snapshot.calculation_mode not in self._SUPPORTED_CALCULATION_MODES:
            raise SymbolSpecificationMappingError("symbol calculation mode is unsupported")
        for field_name, value in (
            ("point", snapshot.point),
            ("tick_size", snapshot.tick_size),
            ("tick_value", snapshot.tick_value),
            ("tick_value_profit", snapshot.tick_value_profit),
            ("tick_value_loss", snapshot.tick_value_loss),
            ("contract_size", snapshot.contract_size),
            ("volume_min", snapshot.volume_min),
            ("volume_max", snapshot.volume_max),
            ("volume_step", snapshot.volume_step),
        ):
            if value <= Decimal(0):
                raise SymbolSpecificationMappingError(f"{field_name} must be positive")
        if snapshot.volume_max < snapshot.volume_min:
            raise SymbolSpecificationMappingError("broker volume range is inverted")
        if snapshot.tick_size % snapshot.point != Decimal(0):
            raise SymbolSpecificationMappingError("tick size is not aligned to point")
        if not (snapshot.tick_value == snapshot.tick_value_profit == snapshot.tick_value_loss):
            raise SymbolSpecificationMappingError(
                "current SymbolSpecification cannot represent asymmetric tick values"
            )
        if snapshot.quote_currency != snapshot.profit_currency:
            raise SymbolSpecificationMappingError(
                "supported FX mapping requires quote and profit currencies to match"
            )
        return SymbolSpecification(
            symbol=snapshot.name,
            base_currency=snapshot.base_currency,
            quote_currency=snapshot.quote_currency,
            contract_size=snapshot.contract_size,
            tick_size=snapshot.tick_size,
            tick_value=snapshot.tick_value,
            tick_value_currency=snapshot.profit_currency,
            volume_min=snapshot.volume_min,
            volume_max=snapshot.volume_max,
            volume_step=snapshot.volume_step,
            price_digits=snapshot.digits,
            max_spread_ticks=max_spread_ticks,
        )
