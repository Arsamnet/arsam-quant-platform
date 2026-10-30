"""Deterministic domain builders shared by the test suites."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fx_platform.domain.advisory import AiAssessment, AiAssessmentStatus
from fx_platform.domain.common import TradeSide
from fx_platform.domain.market import (
    AccountSnapshot,
    BrokerFxQuote,
    CurrencyConversionRate,
    InverseConversionRateDerivation,
    MarketSnapshot,
    SymbolSpecification,
    derive_inverse_conversion_rate,
)
from fx_platform.domain.strategy import SignalCandidate

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
MARKET_ID = UUID("10000000-0000-4000-8000-000000000001")
SIGNAL_ID = UUID("20000000-0000-4000-8000-000000000002")
ASSESSMENT_ID = UUID("30000000-0000-4000-8000-000000000003")
REQUEST_ID = UUID("40000000-0000-4000-8000-000000000004")


@dataclass(slots=True)
class FixedClock:
    """Mutable injected clock controlled only by a test."""

    current: datetime = NOW

    def now(self) -> datetime:
        """Return the configured UTC instant."""
        return self.current


def make_market(
    *,
    bid: Decimal = Decimal("1.1000"),
    ask: Decimal = Decimal("1.1002"),
    previous_close: Decimal = Decimal("1.0990"),
    observed_at: datetime = NOW,
    symbol: str = "EURUSD",
) -> MarketSnapshot:
    """Build a valid market snapshot with explicit exact decimals."""
    return MarketSnapshot(
        snapshot_id=MARKET_ID,
        symbol=symbol,
        observed_at=observed_at,
        bid=bid,
        ask=ask,
        previous_close=previous_close,
    )


def make_account(
    *,
    observed_at: datetime = NOW,
    balance: Decimal = Decimal(10000),
    equity: Decimal = Decimal(10000),
    daily_realized_pnl: Decimal = Decimal(0),
    open_position_count: int = 0,
    currency: str = "USD",
) -> AccountSnapshot:
    """Build valid point-in-time risk state."""
    return AccountSnapshot(
        account_id="paper-account",
        observed_at=observed_at,
        balance=balance,
        equity=equity,
        daily_realized_pnl=daily_realized_pnl,
        open_position_count=open_position_count,
        currency=currency,
    )


def make_specification(
    *,
    symbol: str = "EURUSD",
    base_currency: str = "EUR",
    quote_currency: str = "USD",
    tick_size: Decimal = Decimal("0.00001"),
    tick_value: Decimal = Decimal(1),
    tick_value_currency: str = "USD",
    max_spread_ticks: int | None = 50,
) -> SymbolSpecification:
    """Build reviewed-style symbol metadata for deterministic tests."""
    return SymbolSpecification(
        symbol=symbol,
        base_currency=base_currency,
        quote_currency=quote_currency,
        contract_size=Decimal(100000),
        tick_size=tick_size,
        tick_value=tick_value,
        tick_value_currency=tick_value_currency,
        volume_min=Decimal("0.01"),
        volume_max=Decimal("0.10"),
        volume_step=Decimal("0.01"),
        price_digits=5 if tick_size == Decimal("0.00001") else 3,
        max_spread_ticks=max_spread_ticks,
    )


def make_conversion_rate(
    *,
    source_currency: str = "JPY",
    target_currency: str = "USD",
    rate: Decimal = Decimal("0.006666666666666666666666666667"),
    observed_at: datetime = NOW,
) -> CurrencyConversionRate:
    """Build an explicit directed currency conversion test input."""
    return CurrencyConversionRate(
        source_currency=source_currency,
        target_currency=target_currency,
        rate=rate,
        observed_at=observed_at,
    )


def make_inverse_conversion_derivation(
    *,
    source_currency: str = "JPY",
    target_currency: str = "USD",
    source_symbol: str = "USDJPY",
    pair_base_currency: str = "USD",
    pair_quote_currency: str = "JPY",
    bid: Decimal = Decimal("157.776"),
    ask: Decimal = Decimal("157.786"),
    observed_at: datetime = NOW,
) -> InverseConversionRateDerivation:
    """Build an audited exact-inverse conversion derivation."""
    return derive_inverse_conversion_rate(
        source_currency=source_currency,
        target_currency=target_currency,
        broker_quote=BrokerFxQuote(
            source_symbol=source_symbol,
            base_currency=pair_base_currency,
            quote_currency=pair_quote_currency,
            bid=bid,
            ask=ask,
            observed_at=observed_at,
        ),
    )


def make_signal(
    *,
    side: TradeSide = TradeSide.BUY,
    entry_price: Decimal = Decimal("1.1002"),
    stop_loss: Decimal | None = Decimal("1.0992"),
    take_profit: Decimal | None = Decimal("1.1022"),
    volume: Decimal = Decimal("0.01"),
    created_at: datetime = NOW,
    symbol: str = "EURUSD",
) -> SignalCandidate:
    """Build a strategy candidate, including deliberately unsafe variants for risk tests."""
    return SignalCandidate(
        signal_id=SIGNAL_ID,
        market_snapshot_id=MARKET_ID,
        strategy_name="test_strategy",
        strategy_version="1.0.0",
        created_at=created_at,
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        volume=volume,
    )


def make_assessment(
    *,
    status: AiAssessmentStatus = AiAssessmentStatus.DISABLED,
    direction: TradeSide | None = None,
    signal_id: UUID = SIGNAL_ID,
    confidence: Decimal | None = None,
    uncertainty: Decimal | None = None,
) -> AiAssessment:
    """Build bounded AI advice tied to the default signal."""
    default_confidence = (
        Decimal("0.75") if status is AiAssessmentStatus.AVAILABLE else Decimal(0)
    )
    default_uncertainty = (
        Decimal("0.25") if status is AiAssessmentStatus.AVAILABLE else Decimal(1)
    )
    return AiAssessment(
        assessment_id=ASSESSMENT_ID,
        signal_id=signal_id,
        created_at=NOW,
        status=status,
        direction_preference=direction,
        confidence=default_confidence if confidence is None else confidence,
        market_regime="uncertain",
        uncertainty=default_uncertainty if uncertainty is None else uncertainty,
        reasoning_tags=("test_fixture",),
    )
