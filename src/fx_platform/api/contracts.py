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
from fx_platform.domain.common import TradeSide
from fx_platform.domain.execution import (
    ExecutionResult,
    ExecutionStatus,
    ReconciliationStatus,
)
from fx_platform.domain.market import (
    AccountSnapshot,
    BrokerFxQuote,
    CurrencyConversionRate,
    InverseConversionRateDerivation,
    MarketSnapshot,
    derive_inverse_conversion_rate,
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


class InverseConversionQuoteRequest(_ContractModel):
    """Explicit request to derive a directed rate from one exact inverse broker pair."""

    source_currency: str = Field(pattern=r"^[A-Z]{3}$")
    target_currency: str = Field(pattern=r"^[A-Z]{3}$")
    source_symbol: str = Field(pattern=r"^[A-Z]{6}$")
    pair_base_currency: str = Field(pattern=r"^[A-Z]{3}$")
    pair_quote_currency: str = Field(pattern=r"^[A-Z]{3}$")
    bid: ExactDecimal
    ask: ExactDecimal
    observed_at: AwareDatetime

    @field_validator("observed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        """Normalize the caller-supplied broker observation to UTC."""
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_derivation(self) -> Self:
        """Reject anything other than one valid exact-pair inverse derivation."""
        self.to_domain()
        return self

    def to_domain(self) -> InverseConversionRateDerivation:
        """Derive and retain an auditable directed conversion rate."""
        return derive_inverse_conversion_rate(
            source_currency=self.source_currency,
            target_currency=self.target_currency,
            broker_quote=BrokerFxQuote(
                source_symbol=self.source_symbol,
                base_currency=self.pair_base_currency,
                quote_currency=self.pair_quote_currency,
                bid=self.bid,
                ask=self.ask,
                observed_at=self.observed_at,
            ),
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
    inverse_conversion_quotes: tuple[InverseConversionQuoteRequest, ...] = ()

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
            inverse_conversion_derivations=tuple(
                quote.to_domain() for quote in self.inverse_conversion_quotes
            ),
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
    trading_mode: Literal["paper", "demo"]
    ai_mode: str
    node_id: str


class DemoExecutionIntentResponse(_ContractModel):
    """Strict decimal-string work item consumed only by the localhost MQL5 EA."""

    schema_version: Literal["1.0"]
    execution_id: UUID
    intent_id: UUID
    request_id: UUID
    node_id: str
    created_at: AwareDatetime
    expires_at: AwareDatetime
    symbol: str
    side: Literal["buy", "sell"]
    order_type: Literal["market"]
    volume: str
    requested_price: str
    stop_loss: str
    take_profit: str
    maximum_spread: str
    risk_fingerprint: str
    request_fingerprint: str
    nonce: str
    strategy_name: str
    strategy_version: str
    risk_decision_id: UUID
    signal_id: UUID


class DemoExecutionResultRequest(_ContractModel):
    """Broker result reported by the execution guard without account credentials."""

    schema_version: Literal["1.0"]
    execution_id: UUID
    intent_id: UUID
    status: ExecutionStatus
    broker_retcode: int
    broker_retcode_description: str = Field(min_length=1, max_length=256)
    broker_order_id: int | None = Field(default=None, ge=0)
    broker_deal_id: int | None = Field(default=None, ge=0)
    requested_volume: ExactDecimal
    filled_volume: ExactDecimal
    requested_price: ExactDecimal
    executed_price: ExactDecimal | None = None
    stop_loss: ExactDecimal
    take_profit: ExactDecimal
    submitted_at: AwareDatetime | None = None
    executed_at: AwareDatetime | None = None
    reported_at: AwareDatetime
    symbol: str = Field(pattern=r"^[A-Z]{6,12}$")
    side: TradeSide
    reconciliation_status: ReconciliationStatus
    reason: str = Field(min_length=1, max_length=512)

    @field_validator("submitted_at", "executed_at", "reported_at")
    @classmethod
    def normalize_result_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        forbidden = {
            ExecutionStatus.PAPER_FILLED,
            ExecutionStatus.PENDING,
            ExecutionStatus.CLAIMED,
            ExecutionStatus.DUPLICATE,
        }
        if self.status in forbidden:
            raise ValueError("status is not reportable by the execution guard")
        if min(self.requested_volume, self.filled_volume, self.requested_price) < Decimal(0):
            raise ValueError("result financial values must not be negative")
        if (
            self.requested_volume <= Decimal(0)
            or self.stop_loss <= Decimal(0)
            or self.take_profit <= Decimal(0)
        ):
            raise ValueError("requested volume and broker protection must be positive")
        if self.status is ExecutionStatus.POSITION_CONFIRMED and (
            self.reconciliation_status is not ReconciliationStatus.CONFIRMED
        ):
            raise ValueError("position confirmation requires confirmed reconciliation")
        broker_fill_statuses = {
            ExecutionStatus.FILLED,
            ExecutionStatus.PARTIALLY_FILLED,
            ExecutionStatus.POSITION_CONFIRMED,
        }
        if self.status in broker_fill_statuses and (
            self.filled_volume <= Decimal(0)
            or self.executed_price is None
            or self.executed_price <= Decimal(0)
            or not any(
                identifier is not None and identifier > 0
                for identifier in (self.broker_order_id, self.broker_deal_id)
            )
        ):
            raise ValueError("broker fill status requires positive execution facts")
        if self.status is ExecutionStatus.SUBMITTED and (
            self.broker_order_id is None or self.broker_order_id <= 0
        ):
            raise ValueError("submitted status requires a positive broker order identifier")
        if self.status is ExecutionStatus.REJECTED and self.filled_volume != Decimal(0):
            raise ValueError("rejected status cannot report filled volume")
        expected_reconciliation = {
            ExecutionStatus.REJECTED: {ReconciliationStatus.FAILED},
            ExecutionStatus.UNKNOWN: {ReconciliationStatus.UNKNOWN},
            ExecutionStatus.RECONCILIATION_FAILED: {
                ReconciliationStatus.FAILED,
                ReconciliationStatus.UNKNOWN,
            },
            ExecutionStatus.SUBMITTED: {
                ReconciliationStatus.PENDING,
                ReconciliationStatus.UNKNOWN,
            },
            ExecutionStatus.FILLED: {
                ReconciliationStatus.PENDING,
                ReconciliationStatus.UNKNOWN,
            },
            ExecutionStatus.PARTIALLY_FILLED: {
                ReconciliationStatus.PENDING,
                ReconciliationStatus.UNKNOWN,
            },
            ExecutionStatus.POSITION_CONFIRMED: {ReconciliationStatus.CONFIRMED},
        }
        if self.reconciliation_status not in expected_reconciliation[self.status]:
            raise ValueError("execution and reconciliation statuses are inconsistent")
        return self

    def to_domain(self) -> ExecutionResult:
        return ExecutionResult(
            execution_id=self.execution_id,
            intent_id=self.intent_id,
            completed_at=self.reported_at,
            status=self.status,
            message=self.reason,
            broker_retcode=self.broker_retcode,
            broker_retcode_description=self.broker_retcode_description,
            broker_order_id=self.broker_order_id,
            broker_deal_id=self.broker_deal_id,
            requested_volume=self.requested_volume,
            filled_volume=self.filled_volume,
            requested_price=self.requested_price,
            executed_price=self.executed_price,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            submitted_at=self.submitted_at,
            executed_at=self.executed_at,
            reported_at=self.reported_at,
            symbol=self.symbol,
            side=self.side,
            reconciliation_status=self.reconciliation_status,
        )


class DemoExecutionStatusResponse(_ContractModel):
    """Non-sensitive local execution state for operator and EA startup checks."""

    schema_version: Literal["1.0"] = "1.0"
    trading_mode: Literal["demo"] = "demo"
    execution_enabled: bool
    live_mode: Literal["forbidden"] = "forbidden"
    node_id: str
    counts: dict[str, int]


class DemoExecutionAck(_ContractModel):
    """Idempotent result-ingestion acknowledgement."""

    schema_version: Literal["1.0"] = "1.0"
    accepted: Literal[True] = True
    execution_id: UUID
    status: ExecutionStatus
