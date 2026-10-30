"""Strict local-file adapter for the read-only autonomous MT5 snapshot probe."""

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid5

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from fx_platform.application.autonomy import (
    AutonomousMarketObservation,
    AutonomousSnapshot,
    AutonomousSnapshotError,
)
from fx_platform.domain.market import AccountSnapshot, MarketSnapshot

_SNAPSHOT_NAMESPACE = UUID("4bb05014-14e1-4cf6-8e8a-92665dbd8eaf")
_RETAIL_HEDGING_MARGIN_MODE = 2
_FULL_TRADE_MODE = 4


def _decimal_string(value: object) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("financial values must be JSON strings")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("invalid decimal string") from error
    if not parsed.is_finite():
        raise ValueError("financial values must be finite")
    return parsed


ExactDecimal = Annotated[Decimal, BeforeValidator(_decimal_string)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _Broker(_Model):
    company: str
    server: str


class _Terminal(_Model):
    connected: bool


class _Account(_Model):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    trade_mode_code: int
    leverage: int
    margin_mode_code: int
    trade_allowed: bool
    automated_trading_allowed: bool
    balance: ExactDecimal
    equity: ExactDecimal
    daily_realized_pnl: ExactDecimal
    open_position_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_financials(self) -> "_Account":
        if self.balance <= 0 or self.equity < 0:
            raise ValueError("invalid autonomous account financials")
        return self


class _Symbol(_Model):
    name: str = Field(pattern=r"^[A-Z]{6,12}$")
    base_currency: str = Field(pattern=r"^[A-Z]{3}$")
    quote_currency: str = Field(pattern=r"^[A-Z]{3}$")
    bid: ExactDecimal
    ask: ExactDecimal
    previous_close: ExactDecimal
    observed_at: AwareDatetime
    decision_bar_time: AwareDatetime
    tick_age_seconds: int = Field(ge=0)
    trade_mode_code: int

    @field_validator("observed_at", "decision_bar_time")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_prices(self) -> "_Symbol":
        if min(self.bid, self.ask, self.previous_close) <= 0 or self.ask < self.bid:
            raise ValueError("invalid autonomous market prices")
        return self


class _Snapshot(_Model):
    schema_version: Literal["1.0"]
    mode: Literal["autonomous_demo_snapshot"]
    source_type: Literal["mql5_autonomous_probe"]
    acquired_at: AwareDatetime
    broker: _Broker
    terminal: _Terminal
    account: _Account
    symbols: tuple[_Symbol, ...]

    @field_validator("acquired_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class FileAutonomousSnapshotSource:
    """Parse and validate a local MT5-generated snapshot without network access."""

    def __init__(
        self,
        *,
        path: Path,
        expected_broker_company: str,
        expected_broker_server: str,
        expected_account_currency: str,
        expected_leverage: int,
        allowed_symbols: frozenset[str],
        account_id: str,
        max_tick_age_seconds: int,
    ) -> None:
        if max_tick_age_seconds < 1:
            raise ValueError("max_tick_age_seconds must be positive")
        self._path = path
        self._expected_broker_company = expected_broker_company
        self._expected_broker_server = expected_broker_server
        self._expected_account_currency = expected_account_currency
        self._expected_leverage = expected_leverage
        self._allowed_symbols = allowed_symbols
        self._account_id = account_id
        self._max_tick_age_seconds = max_tick_age_seconds

    def read(self) -> AutonomousSnapshot:
        """Read one complete snapshot or reject it without returning partial state."""
        try:
            raw = self._path.read_text(encoding="utf-8")
            payload = _Snapshot.model_validate_json(raw)
        except (OSError, UnicodeError, ValidationError, json.JSONDecodeError) as error:
            raise AutonomousSnapshotError("autonomous snapshot unavailable or malformed") from error

        self._validate_identity(payload)
        account = AccountSnapshot(
            account_id=self._account_id,
            observed_at=payload.acquired_at,
            balance=payload.account.balance,
            equity=payload.account.equity,
            daily_realized_pnl=payload.account.daily_realized_pnl,
            open_position_count=payload.account.open_position_count,
            currency=payload.account.currency,
        )
        markets = tuple(self._to_market(symbol) for symbol in payload.symbols)
        return AutonomousSnapshot(
            acquired_at=payload.acquired_at,
            account=account,
            markets=markets,
        )

    def _validate_identity(self, payload: _Snapshot) -> None:
        if (
            payload.broker.company != self._expected_broker_company
            or payload.broker.server != self._expected_broker_server
        ):
            raise AutonomousSnapshotError("autonomous broker/server identity mismatch")
        account = payload.account
        if (
            not payload.terminal.connected
            or account.currency != self._expected_account_currency
            or account.trade_mode_code != 0
            or account.margin_mode_code != _RETAIL_HEDGING_MARGIN_MODE
            or account.leverage != self._expected_leverage
            or not account.trade_allowed
            or not account.automated_trading_allowed
        ):
            raise AutonomousSnapshotError("autonomous DEMO account identity/mode mismatch")
        symbols = {symbol.name for symbol in payload.symbols}
        if symbols != self._allowed_symbols:
            raise AutonomousSnapshotError("autonomous symbol set differs from reviewed allowlist")
        for symbol in payload.symbols:
            if symbol.trade_mode_code != _FULL_TRADE_MODE:
                raise AutonomousSnapshotError(f"{symbol.name} is not trade-enabled")
            if symbol.tick_age_seconds > self._max_tick_age_seconds:
                raise AutonomousSnapshotError(f"{symbol.name} quote is stale")
            if symbol.name != symbol.base_currency + symbol.quote_currency:
                raise AutonomousSnapshotError(f"{symbol.name} currency identity mismatch")

    @staticmethod
    def _to_market(symbol: _Symbol) -> AutonomousMarketObservation:
        snapshot_key = (
            f"{symbol.name}:{symbol.observed_at.isoformat()}:{symbol.bid}:{symbol.ask}:"
            f"{symbol.previous_close}"
        )
        market = MarketSnapshot(
            snapshot_id=uuid5(_SNAPSHOT_NAMESPACE, snapshot_key),
            symbol=symbol.name,
            observed_at=symbol.observed_at,
            bid=symbol.bid,
            ask=symbol.ask,
            previous_close=symbol.previous_close,
        )
        return AutonomousMarketObservation(
            market=market,
            decision_bar_time=symbol.decision_bar_time,
            base_currency=symbol.base_currency,
            quote_currency=symbol.quote_currency,
        )
