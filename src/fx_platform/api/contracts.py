"""Strict v1 HTTP contracts and exact-decimal conversion boundaries."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from fx_platform.application.models import DecisionCommand, DecisionOutcome
from fx_platform.domain.market import (
    AccountSnapshot,
    CurrencyConversionRate,
    MarketSnapshot,
)


def _parse_exact_decimal(value: object) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("financial decimal values must be JSON strings")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("invalid decimal string") from error
    if not parsed.is_finite():
        raise ValueError("decimal value must be finite")
    return parsed


ExactDecimal = Annotated[Decimal, BeforeValidator(_parse_exact_decimal)]


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MarketSnapshotRequest(_ContractModel):
    """Exact point-in-time Bid/Ask input from the local trading node."""

    snapshot_id: UUID
    symbol: str = Field(pattern=r"^[A-Z]{6,12}$")
    observed_at: AwareDatetime
    bid: ExactDecimal
    ask: ExactDecimal
    previous_close: ExactDecimal

    @field_validator("observed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        """Normalize accepted aware offsets to UTC before domain conversion."""
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_prices(self) -> Self:
        """Reject invalid prices at the HTTP boundary."""
        if min(self.bid, self.ask, self.previous_close) <= Decimal(0):
            raise ValueError("market prices must be greater than zero")
        if self.ask < self.bid:
            raise ValueError("ask must be greater than or equal to bid")
        return self

    def to_domain(self) -> MarketSnapshot:
        """Convert validated API data into an immutable domain snapshot."""
        return MarketSnapshot(
            snapshot_id=self.snapshot_id,
            symbol=self.symbol,
            observed_at=self.observed_at,
            bid=self.bid,
            ask=self.ask,
            previous_close=self.previous_close,
        )


class AccountSnapshotRequest(_ContractModel):
    """Risk-relevant account input with no broker credentials."""

    account_id: str = Field(min_length=1, max_length=64)
    observed_at: AwareDatetime
    balance: ExactDecimal
    equity: ExactDecimal
    daily_realized_pnl: ExactDecimal
    open_position_count: int = Field(ge=0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")

    @field_validator("observed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        """Normalize accepted aware offsets to UTC before domain conversion."""
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_account_values(self) -> Self:
        """Reject impossible account values before risk orchestration."""
        if self.balance <= Decimal(0):
            raise ValueError("balance must be greater than zero")
        if self.equity < Decimal(0):
            raise ValueError("equity must not be negative")
        return self

    def to_domain(self) -> AccountSnapshot:
        """Convert validated API data into immutable risk state."""
        return AccountSnapshot(
            account_id=self.account_id,
            observed_at=self.observed_at,
            balance=self.balance,
            equity=self.equity,
            daily_realized_pnl=self.daily_realized_pnl,
            open_position_count=self.open_position_count,
            currency=self.currency,
        )


class CurrencyConversionRateRequest(_ContractModel):
    """Directed point-in-time rate supplied explicitly by the local node."""

    source_currency: str = Field(pattern=r"^[A-Z]{3}$")
    target_currency: str = Field(pattern=r"^[A-Z]{3}$")
    rate: ExactDecimal
    observed_at: AwareDatetime

    @field_validator("observed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        """Normalize an aware conversion timestamp to UTC."""
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_rate(self) -> Self:
        """Reject non-positive or identity conversions at the boundary."""
        if self.rate <= Decimal(0):
            raise ValueError("conversion rate must be greater than zero")
        if self.source_currency == self.target_currency:
            raise ValueError("conversion currencies must be different")
        return self

    def to_domain(self) -> CurrencyConversionRate:
        """Convert the validated wire value to an immutable domain input."""
        return CurrencyConversionRate(
            source_currency=self.source_currency,
            target_currency=self.target_currency,
            rate=self.rate,
            observed_at=self.observed_at,
        )


class DecisionRequest(_ContractModel):
    """Versioned MQL5-to-Python decision request envelope."""

    schema_version: Literal["1.0"]
    request_id: UUID
    timestamp: AwareDatetime
    nonce: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    node_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    market: MarketSnapshotRequest
    account: AccountSnapshotRequest
    conversion_rates: tuple[CurrencyConversionRateRequest, ...] = ()

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        """Normalize the request timestamp to UTC."""
        return value.astimezone(UTC)

    def to_command(self) -> DecisionCommand:
        """Convert a valid wire contract to a framework-independent command."""
        return DecisionCommand(
            request_id=self.request_id,
            request_timestamp=self.timestamp,
            nonce=self.nonce,
            schema_version=self.schema_version,
            node_id=self.node_id,
            market=self.market.to_domain(),
            account=self.account.to_domain(),
            conversion_rates=tuple(rate.to_domain() for rate in self.conversion_rates),
        )


class DecisionResponse(_ContractModel):
    """Traceable decision response; absence of an execution ID means no execution occurred."""

    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    status: str
    signal_id: UUID | None
    risk_decision_id: UUID | None
    execution_id: UUID | None
    execution_status: str | None
    reasons: tuple[str, ...]

    @classmethod
    def from_outcome(cls, outcome: DecisionOutcome) -> Self:
        """Build the response without exposing internal objects or exceptions."""
        return cls(
            request_id=outcome.request_id,
            status=outcome.status.value,
            signal_id=outcome.signal_id,
            risk_decision_id=outcome.risk_decision_id,
            execution_id=outcome.execution_id,
            execution_status=None
            if outcome.execution_status is None
            else outcome.execution_status.value,
            reasons=outcome.reasons,
        )


class HealthResponse(_ContractModel):
    """Non-sensitive process health and safety-mode response."""

    status: Literal["ok"] = "ok"
    version: str
    trading_mode: Literal["paper"] = "paper"
    ai_mode: str
    node_id: str
