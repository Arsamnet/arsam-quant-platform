"""Deterministic account-currency stop-loss exposure calculation."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from fx_platform.domain.common import require_utc
from fx_platform.domain.market import (
    CurrencyConversionFailure,
    CurrencyConversionRate,
    SymbolSpecification,
    convert_currency,
)
from fx_platform.domain.strategy import SignalCandidate

RiskCalculationFailure = CurrencyConversionFailure


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeRiskCalculation:
    """Either an exact account-currency amount or one explicit failure."""

    amount: Decimal | None
    failure: RiskCalculationFailure | None

    def __post_init__(self) -> None:
        if (self.amount is None) == (self.failure is None):
            raise ValueError("risk calculation must contain exactly one result")


class AccountCurrencyRiskCalculator:
    """Calculate tick-value exposure using only explicit domain inputs."""

    def calculate(
        self,
        *,
        signal: SignalCandidate,
        specification: SymbolSpecification,
        account_currency: str,
        conversion_rates: tuple[CurrencyConversionRate, ...],
        evaluated_at: datetime,
        max_conversion_age: timedelta,
        max_future_skew: timedelta,
    ) -> TradeRiskCalculation | None:
        """Return ``None`` when stop/volume validity prevents a meaningful amount."""
        require_utc(evaluated_at, "evaluated_at")
        if signal.stop_loss is None or signal.volume <= Decimal(0):
            return None

        ticks_to_stop = abs(signal.entry_price - signal.stop_loss) / specification.tick_size
        risk_in_tick_currency = ticks_to_stop * specification.tick_value * signal.volume
        if specification.tick_value_currency == account_currency:
            return TradeRiskCalculation(amount=risk_in_tick_currency, failure=None)

        converted = convert_currency(
            amount=risk_in_tick_currency,
            source_currency=specification.tick_value_currency,
            target_currency=account_currency,
            conversion_rates=conversion_rates,
            evaluated_at=evaluated_at,
            max_conversion_age=max_conversion_age,
            max_future_skew=max_future_skew,
        )
        return TradeRiskCalculation(amount=converted.amount, failure=converted.failure)
