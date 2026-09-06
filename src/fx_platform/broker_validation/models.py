"""Immutable canonical broker-contract and validation-report values."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from fx_platform.domain.common import require_finite_decimal, require_utc
from fx_platform.serialization import canonical_json, fingerprint

BROKER_SNAPSHOT_SCHEMA_VERSION = "1.0"
BROKER_REPORT_SCHEMA_VERSION = "1.0"
READ_ONLY_MODE = "read_only_metadata_probe"
_CURRENCY_CODE_LENGTH = 3
_SHA256_HEX_LENGTH = 64


class SnapshotSourceType(StrEnum):
    """Permitted authoritative metadata acquisition mechanisms."""

    MQL5_METADATA_PROBE = "mql5_metadata_probe"


class AccountTradeMode(StrEnum):
    """MT5 account environment without retaining an account login."""

    DEMO = "demo"
    CONTEST = "contest"
    REAL = "real"
    UNKNOWN = "unknown"


class AccountPositionMode(StrEnum):
    """Position-accounting mode reported by MT5 margin mode."""

    RETAIL_NETTING = "retail_netting"
    EXCHANGE = "exchange"
    RETAIL_HEDGING = "retail_hedging"
    UNKNOWN = "unknown"


class SymbolTradeMode(StrEnum):
    """Point-in-time symbol trade permission."""

    DISABLED = "disabled"
    LONG_ONLY = "long_only"
    SHORT_ONLY = "short_only"
    CLOSE_ONLY = "close_only"
    FULL = "full"
    UNKNOWN = "unknown"


class CalculationMode(StrEnum):
    """Normalized MT5 symbol calculation modes."""

    FOREX = "forex"
    FOREX_NO_LEVERAGE = "forex_no_leverage"
    FUTURES = "futures"
    CFD = "cfd"
    CFD_INDEX = "cfd_index"
    CFD_LEVERAGE = "cfd_leverage"
    EXCHANGE_STOCKS = "exchange_stocks"
    EXCHANGE_FUTURES = "exchange_futures"
    EXCHANGE_FUTURES_FORTS = "exchange_futures_forts"
    EXCHANGE_BONDS = "exchange_bonds"
    EXCHANGE_STOCKS_MOEX = "exchange_stocks_moex"
    EXCHANGE_BONDS_MOEX = "exchange_bonds_moex"
    SERVICE_COLLATERAL = "service_collateral"
    UNKNOWN = "unknown"


class SwapMode(StrEnum):
    """Normalized MT5 swap calculation modes."""

    DISABLED = "disabled"
    POINTS = "points"
    SYMBOL_CURRENCY = "symbol_currency"
    MARGIN_CURRENCY = "margin_currency"
    DEPOSIT_CURRENCY = "deposit_currency"
    INTEREST_CURRENT = "interest_current"
    INTEREST_OPEN = "interest_open"
    REOPEN_CURRENT = "reopen_current"
    REOPEN_BID = "reopen_bid"
    UNKNOWN = "unknown"


class OrderMode(StrEnum):
    """Decoded MT5 order-mode capability bits."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    CLOSE_BY = "close_by"


class FillingMode(StrEnum):
    """Decoded MT5 filling-mode capability bits."""

    FOK = "fill_or_kill"
    IOC = "immediate_or_cancel"
    BOC = "book_or_cancel"


class ExpirationMode(StrEnum):
    """Decoded MT5 expiration-mode capability bits."""

    GTC = "good_till_cancelled"
    DAY = "day"
    SPECIFIED = "specified"
    SPECIFIED_DAY = "specified_day"


class CalculationSide(StrEnum):
    """Hypothetical side used only by read-only calculation functions."""

    BUY = "buy"
    SELL = "sell"


class ValidationSeverity(StrEnum):
    """Severity of one explicit broker-contract check."""

    PASS = "pass"  # noqa: S105 - validation status, not a password
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class ValidationOverallStatus(StrEnum):
    """Stable aggregate report status."""

    PASS = "pass"  # noqa: S105 - validation status, not a password
    WARNING = "warning"
    BLOCKING_MISMATCH = "blocking_mismatch"


class BrokerReadiness(StrEnum):
    """Informational future-execution readiness; it cannot enable trading."""

    READY = "ready"
    NOT_READY = "not_ready"
    UNKNOWN = "unknown"


def _require_text(value: str, field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name} must not be empty")


def _require_currency(value: str, field_name: str) -> None:
    if len(value) != _CURRENCY_CODE_LENGTH or value != value.upper():
        raise ValueError(f"{field_name} must be an uppercase ISO-style currency code")


def _require_nonnegative_decimal(value: Decimal, field_name: str) -> None:
    require_finite_decimal(value, field_name)
    if value < Decimal(0):
        raise ValueError(f"{field_name} must not be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class BrokerTerminalSnapshot:
    """Non-secret terminal identity and time-context evidence."""

    name: str
    build: int
    version: str | None
    connected: bool
    server_time_raw: str | None
    server_utc_offset_minutes: int | None

    def __post_init__(self) -> None:
        _require_text(self.name, "terminal name")
        if self.build < 0:
            raise ValueError("terminal build must not be negative")
        if self.version is not None:
            _require_text(self.version, "terminal version")
        if self.server_utc_offset_minutes is not None and not (
            -24 * 60 <= self.server_utc_offset_minutes <= 24 * 60
        ):
            raise ValueError("server UTC offset is outside the supported range")


@dataclass(frozen=True, slots=True, kw_only=True)
class BrokerAccountSnapshot:
    """Calculation-relevant account metadata without password or raw login."""

    currency: str
    trade_mode: AccountTradeMode
    trade_mode_code: int
    leverage: int
    position_mode: AccountPositionMode
    margin_mode_code: int
    trade_allowed: bool
    automated_trading_allowed: bool
    account_id_hash: str | None = None

    def __post_init__(self) -> None:
        _require_currency(self.currency, "account currency")
        if self.leverage <= 0:
            raise ValueError("account leverage must be positive")
        if self.trade_mode_code < 0 or self.margin_mode_code < 0:
            raise ValueError("account mode codes must not be negative")
        if self.account_id_hash is not None and (
            len(self.account_id_hash) != _SHA256_HEX_LENGTH
            or any(character not in "0123456789abcdef" for character in self.account_id_hash)
        ):
            raise ValueError("account_id_hash must be lowercase SHA-256 when provided")


@dataclass(frozen=True, slots=True, kw_only=True)
class BrokerSymbolSnapshot:
    """Canonical static and point-in-time MT5 symbol metadata."""

    name: str
    base_currency: str
    quote_currency: str
    profit_currency: str
    margin_currency: str
    digits: int
    point: Decimal
    tick_size: Decimal
    tick_value: Decimal
    tick_value_profit: Decimal
    tick_value_loss: Decimal
    contract_size: Decimal
    volume_min: Decimal
    volume_max: Decimal
    volume_step: Decimal
    volume_limit: Decimal
    bid: Decimal
    ask: Decimal
    reported_spread_points: int
    spread_is_floating: bool
    trade_mode: SymbolTradeMode
    trade_mode_code: int
    order_modes: frozenset[OrderMode]
    order_mode_unknown_bits: int
    filling_modes: frozenset[FillingMode]
    filling_mode_unknown_bits: int
    expiration_modes: frozenset[ExpirationMode]
    expiration_mode_unknown_bits: int
    stop_level_points: int
    freeze_level_points: int
    calculation_mode: CalculationMode
    calculation_mode_code: int
    swap_mode: SwapMode
    swap_mode_code: int
    swap_long: Decimal
    swap_short: Decimal
    rollover_day: int
    margin_initial: Decimal
    margin_maintenance: Decimal
    observed_at: datetime

    def __post_init__(self) -> None:
        require_utc(self.observed_at, "symbol observed_at")
        if not self.name or self.name != self.name.upper():
            raise ValueError("symbol name must be non-empty uppercase text")
        for field_name, currency in (
            ("base_currency", self.base_currency),
            ("quote_currency", self.quote_currency),
            ("profit_currency", self.profit_currency),
            ("margin_currency", self.margin_currency),
        ):
            _require_currency(currency, field_name)
        for field_name, decimal_value in (
            ("point", self.point),
            ("tick_size", self.tick_size),
            ("tick_value", self.tick_value),
            ("tick_value_profit", self.tick_value_profit),
            ("tick_value_loss", self.tick_value_loss),
            ("contract_size", self.contract_size),
            ("volume_min", self.volume_min),
            ("volume_max", self.volume_max),
            ("volume_step", self.volume_step),
            ("volume_limit", self.volume_limit),
            ("bid", self.bid),
            ("ask", self.ask),
            ("margin_initial", self.margin_initial),
            ("margin_maintenance", self.margin_maintenance),
        ):
            _require_nonnegative_decimal(decimal_value, field_name)
        for field_name, value in (("swap_long", self.swap_long), ("swap_short", self.swap_short)):
            require_finite_decimal(value, field_name)
        for field_name, integer_value in (
            ("digits", self.digits),
            ("reported_spread_points", self.reported_spread_points),
            ("trade_mode_code", self.trade_mode_code),
            ("order_mode_unknown_bits", self.order_mode_unknown_bits),
            ("filling_mode_unknown_bits", self.filling_mode_unknown_bits),
            ("expiration_mode_unknown_bits", self.expiration_mode_unknown_bits),
            ("stop_level_points", self.stop_level_points),
            ("freeze_level_points", self.freeze_level_points),
            ("calculation_mode_code", self.calculation_mode_code),
            ("swap_mode_code", self.swap_mode_code),
            ("rollover_day", self.rollover_day),
        ):
            if integer_value < 0:
                raise ValueError(f"{field_name} must not be negative")

    @property
    def observed_spread(self) -> Decimal:
        """Return the exact observed Ask minus Bid without repair."""
        return self.ask - self.bid

    @property
    def reported_spread(self) -> Decimal:
        """Return terminal spread points as a price distance."""
        return self.point * self.reported_spread_points

    def accepts_volume(self, volume: Decimal) -> bool:
        """Return whether volume is on the broker-reported per-order grid."""
        if (
            not volume.is_finite()
            or self.volume_step <= Decimal(0)
            or volume < self.volume_min
            or volume > self.volume_max
        ):
            return False
        return (volume - self.volume_min) % self.volume_step == Decimal(0)

    def accepts_price(self, price: Decimal) -> bool:
        """Return whether a price is aligned to the broker tick-size grid."""
        return (
            price.is_finite()
            and price >= Decimal(0)
            and self.tick_size > 0
            and price % self.tick_size == 0
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BrokerProfitCalculation:
    """Deterministic input/output from read-only MT5 OrderCalcProfit."""

    symbol: str
    side: CalculationSide
    volume: Decimal
    open_price: Decimal
    close_price: Decimal
    calculated_profit: Decimal | None
    success: bool
    error_code: int
    observed_at: datetime

    def __post_init__(self) -> None:
        require_utc(self.observed_at, "profit calculation observed_at")
        if not self.symbol or self.symbol != self.symbol.upper():
            raise ValueError("calculation symbol must be uppercase")
        for field_name, value in (
            ("volume", self.volume),
            ("open_price", self.open_price),
            ("close_price", self.close_price),
        ):
            _require_nonnegative_decimal(value, field_name)
        if self.calculated_profit is not None:
            require_finite_decimal(self.calculated_profit, "calculated_profit")
        if self.success != (self.calculated_profit is not None):
            raise ValueError("successful profit calculations require exactly one result")
        if self.error_code < 0:
            raise ValueError("calculation error code must not be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class BrokerMarginCalculation:
    """Deterministic input/output from read-only MT5 OrderCalcMargin."""

    symbol: str
    side: CalculationSide
    volume: Decimal
    price: Decimal
    calculated_margin: Decimal | None
    success: bool
    error_code: int
    observed_at: datetime

    def __post_init__(self) -> None:
        require_utc(self.observed_at, "margin calculation observed_at")
        if not self.symbol or self.symbol != self.symbol.upper():
            raise ValueError("calculation symbol must be uppercase")
        for field_name, value in (("volume", self.volume), ("price", self.price)):
            _require_nonnegative_decimal(value, field_name)
        if self.calculated_margin is not None:
            _require_nonnegative_decimal(self.calculated_margin, "calculated_margin")
        if self.success != (self.calculated_margin is not None):
            raise ValueError("successful margin calculations require exactly one result")
        if self.error_code < 0:
            raise ValueError("calculation error code must not be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class BrokerContractSnapshot:
    """One canonical, auditable acquisition from a read-only MT5 terminal."""

    schema_version: str
    mode: str
    source_type: SnapshotSourceType
    acquired_at: datetime
    broker_company: str
    broker_server: str
    terminal: BrokerTerminalSnapshot
    account: BrokerAccountSnapshot
    requested_symbols: tuple[str, ...]
    symbols: tuple[BrokerSymbolSnapshot, ...]
    profit_calculations: tuple[BrokerProfitCalculation, ...] = ()
    margin_calculations: tuple[BrokerMarginCalculation, ...] = ()

    def __post_init__(self) -> None:
        require_utc(self.acquired_at, "acquired_at")
        if self.schema_version != BROKER_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("unsupported broker snapshot schema version")
        if self.mode != READ_ONLY_MODE:
            raise ValueError("broker snapshot does not declare the read-only safety mode")
        _require_text(self.broker_company, "broker company")
        _require_text(self.broker_server, "broker server")
        if not self.requested_symbols or any(
            not symbol or symbol != symbol.upper() for symbol in self.requested_symbols
        ):
            raise ValueError("requested_symbols must contain uppercase symbols")
        if len(set(self.requested_symbols)) != len(self.requested_symbols):
            raise ValueError("requested_symbols must be unique")
        names = tuple(symbol.name for symbol in self.symbols)
        if len(set(names)) != len(names):
            raise ValueError("broker snapshot symbols must be unique")
        if any(symbol.name not in self.requested_symbols for symbol in self.symbols):
            raise ValueError("observed symbols must have been explicitly requested")
        object.__setattr__(self, "requested_symbols", tuple(sorted(self.requested_symbols)))
        object.__setattr__(self, "symbols", tuple(sorted(self.symbols, key=lambda item: item.name)))
        object.__setattr__(
            self,
            "profit_calculations",
            tuple(
                sorted(
                    self.profit_calculations,
                    key=lambda item: canonical_json(_profit_calculation_interchange(item)),
                )
            ),
        )
        object.__setattr__(
            self,
            "margin_calculations",
            tuple(
                sorted(
                    self.margin_calculations,
                    key=lambda item: canonical_json(_margin_calculation_interchange(item)),
                )
            ),
        )

    def symbol(self, name: str) -> BrokerSymbolSnapshot | None:
        """Find a symbol without guessing aliases or broker suffixes."""
        return next((symbol for symbol in self.symbols if symbol.name == name), None)

    def to_interchange_dict(self) -> dict[str, Any]:
        """Return the strict schema-1.0 interchange representation."""
        symbols = tuple(
            sorted((_symbol_interchange(symbol) for symbol in self.symbols), key=canonical_json)
        )
        profit_calculations = tuple(
            sorted(
                (
                    _profit_calculation_interchange(calculation)
                    for calculation in self.profit_calculations
                ),
                key=canonical_json,
            )
        )
        margin_calculations = tuple(
            sorted(
                (
                    _margin_calculation_interchange(calculation)
                    for calculation in self.margin_calculations
                ),
                key=canonical_json,
            )
        )
        return {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "source_type": self.source_type,
            "acquired_at": self.acquired_at,
            "broker": {"company": self.broker_company, "server": self.broker_server},
            "terminal": {
                "name": self.terminal.name,
                "build": self.terminal.build,
                "version": self.terminal.version,
                "connected": self.terminal.connected,
                "server_time_raw": self.terminal.server_time_raw,
                "server_utc_offset_minutes": self.terminal.server_utc_offset_minutes,
            },
            "account": {
                "currency": self.account.currency,
                "trade_mode_code": self.account.trade_mode_code,
                "leverage": self.account.leverage,
                "margin_mode_code": self.account.margin_mode_code,
                "trade_allowed": self.account.trade_allowed,
                "automated_trading_allowed": self.account.automated_trading_allowed,
                "account_id_hash": self.account.account_id_hash,
            },
            "requested_symbols": tuple(sorted(self.requested_symbols)),
            "symbols": symbols,
            "profit_calculations": profit_calculations,
            "margin_calculations": margin_calculations,
        }

    def to_json(self) -> str:
        """Serialize a canonical importable snapshot."""
        return canonical_json(self.to_interchange_dict())

    @property
    def snapshot_fingerprint(self) -> str:
        """Hash complete static and dynamic snapshot content with SHA-256."""
        return fingerprint(self.to_interchange_dict())

    def contract_payload(self) -> dict[str, Any]:
        """Return calculation contract content excluding quotes and other observations."""
        return {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "source_type": self.source_type,
            "broker": {"company": self.broker_company, "server": self.broker_server},
            "terminal": {
                "name": self.terminal.name,
                "build": self.terminal.build,
                "version": self.terminal.version,
            },
            "account": {
                "currency": self.account.currency,
                "trade_mode": self.account.trade_mode,
                "trade_mode_code": self.account.trade_mode_code,
                "position_mode": self.account.position_mode,
                "margin_mode_code": self.account.margin_mode_code,
                "leverage": self.account.leverage,
            },
            "requested_symbols": tuple(sorted(self.requested_symbols)),
            "symbols": tuple(
                sorted((_symbol_contract(symbol) for symbol in self.symbols), key=canonical_json)
            ),
        }

    def dynamic_payload(self) -> dict[str, Any]:
        """Return explicitly point-in-time content excluded from the contract hash."""
        return {
            "acquired_at": self.acquired_at,
            "terminal": {
                "connected": self.terminal.connected,
                "server_time_raw": self.terminal.server_time_raw,
                "server_utc_offset_minutes": self.terminal.server_utc_offset_minutes,
            },
            "account": {
                "trade_allowed": self.account.trade_allowed,
                "automated_trading_allowed": self.account.automated_trading_allowed,
            },
            "symbols": tuple(
                sorted((_symbol_dynamic(symbol) for symbol in self.symbols), key=canonical_json)
            ),
            "profit_calculations": tuple(
                sorted(
                    (
                        _profit_calculation_interchange(calculation)
                        for calculation in self.profit_calculations
                    ),
                    key=canonical_json,
                )
            ),
            "margin_calculations": tuple(
                sorted(
                    (
                        _margin_calculation_interchange(calculation)
                        for calculation in self.margin_calculations
                    ),
                    key=canonical_json,
                )
            ),
        }

    @property
    def contract_fingerprint(self) -> str:
        """Hash stable/calculation metadata while deliberately excluding observations."""
        return fingerprint(self.contract_payload())


@dataclass(frozen=True, slots=True, kw_only=True)
class BrokerValidationCheck:
    """One stable, machine-readable validation result."""

    code: str
    field: str
    severity: ValidationSeverity
    expected: Any
    observed: Any
    message: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("code", self.code),
            ("field", self.field),
            ("message", self.message),
        ):
            _require_text(value, field_name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "field": self.field,
            "severity": self.severity,
            "expected": self.expected,
            "observed": self.observed,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class BrokerValidationReport:
    """Deterministic comparison artifact; readiness never enables execution."""

    schema_version: str
    snapshot_fingerprint: str
    contract_fingerprint: str
    policy_fingerprint: str
    platform_version: str
    symbol: str
    account_currency: str
    validated_at: datetime
    validation_time_semantics: str
    overall_status: ValidationOverallStatus
    readiness: BrokerReadiness
    checks: tuple[BrokerValidationCheck, ...]

    def __post_init__(self) -> None:
        require_utc(self.validated_at, "validated_at")
        if self.schema_version != BROKER_REPORT_SCHEMA_VERSION:
            raise ValueError("unsupported validation report schema version")
        for field_name, value in (
            ("snapshot_fingerprint", self.snapshot_fingerprint),
            ("contract_fingerprint", self.contract_fingerprint),
            ("policy_fingerprint", self.policy_fingerprint),
        ):
            if len(value) != _SHA256_HEX_LENGTH:
                raise ValueError(f"{field_name} must be a SHA-256 fingerprint")
        if not self.checks:
            raise ValueError("validation report must contain checks")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "contract_fingerprint": self.contract_fingerprint,
            "policy_fingerprint": self.policy_fingerprint,
            "platform_version": self.platform_version,
            "symbol": self.symbol,
            "account_currency": self.account_currency,
            "validated_at": self.validated_at,
            "validation_time_semantics": self.validation_time_semantics,
            "overall_status": self.overall_status,
            "readiness": self.readiness,
            "checks": tuple(check.to_dict() for check in self.checks),
        }

    def to_json(self) -> str:
        """Return byte-stable canonical JSON for identical logical inputs."""
        return canonical_json(self.to_dict())


def _symbol_interchange(symbol: BrokerSymbolSnapshot) -> dict[str, Any]:
    return {
        "name": symbol.name,
        "base_currency": symbol.base_currency,
        "quote_currency": symbol.quote_currency,
        "profit_currency": symbol.profit_currency,
        "margin_currency": symbol.margin_currency,
        "digits": symbol.digits,
        "point": symbol.point,
        "tick_size": symbol.tick_size,
        "tick_value": symbol.tick_value,
        "tick_value_profit": symbol.tick_value_profit,
        "tick_value_loss": symbol.tick_value_loss,
        "contract_size": symbol.contract_size,
        "volume_min": symbol.volume_min,
        "volume_max": symbol.volume_max,
        "volume_step": symbol.volume_step,
        "volume_limit": symbol.volume_limit,
        "bid": symbol.bid,
        "ask": symbol.ask,
        "reported_spread_points": symbol.reported_spread_points,
        "spread_is_floating": symbol.spread_is_floating,
        "trade_mode_code": symbol.trade_mode_code,
        "order_mode_mask": _mode_mask(symbol.order_modes, _ORDER_MODE_BITS),
        "filling_mode_mask": _mode_mask(symbol.filling_modes, _FILLING_MODE_BITS),
        "expiration_mode_mask": _mode_mask(symbol.expiration_modes, _EXPIRATION_MODE_BITS),
        "stop_level_points": symbol.stop_level_points,
        "freeze_level_points": symbol.freeze_level_points,
        "calculation_mode_code": symbol.calculation_mode_code,
        "swap_mode_code": symbol.swap_mode_code,
        "swap_long": symbol.swap_long,
        "swap_short": symbol.swap_short,
        "rollover_day": symbol.rollover_day,
        "margin_initial": symbol.margin_initial,
        "margin_maintenance": symbol.margin_maintenance,
        "observed_at": symbol.observed_at,
    } | {
        "order_mode_mask": _mode_mask(symbol.order_modes, _ORDER_MODE_BITS)
        | symbol.order_mode_unknown_bits,
        "filling_mode_mask": _mode_mask(symbol.filling_modes, _FILLING_MODE_BITS)
        | symbol.filling_mode_unknown_bits,
        "expiration_mode_mask": _mode_mask(symbol.expiration_modes, _EXPIRATION_MODE_BITS)
        | symbol.expiration_mode_unknown_bits,
    }


def _symbol_contract(symbol: BrokerSymbolSnapshot) -> dict[str, Any]:
    interchange = _symbol_interchange(symbol)
    dynamic_fields = {
        "bid",
        "ask",
        "reported_spread_points",
        "spread_is_floating",
        "trade_mode_code",
        "tick_value",
        "tick_value_profit",
        "tick_value_loss",
        "observed_at",
    }
    return {key: value for key, value in interchange.items() if key not in dynamic_fields}


def _symbol_dynamic(symbol: BrokerSymbolSnapshot) -> dict[str, Any]:
    return {
        "name": symbol.name,
        "observed_at": symbol.observed_at,
        "bid": symbol.bid,
        "ask": symbol.ask,
        "reported_spread_points": symbol.reported_spread_points,
        "spread_is_floating": symbol.spread_is_floating,
        "trade_mode": symbol.trade_mode,
        "tick_value": symbol.tick_value,
        "tick_value_profit": symbol.tick_value_profit,
        "tick_value_loss": symbol.tick_value_loss,
    }


def _profit_calculation_interchange(calculation: BrokerProfitCalculation) -> dict[str, Any]:
    return {
        "symbol": calculation.symbol,
        "side": calculation.side,
        "volume": calculation.volume,
        "open_price": calculation.open_price,
        "close_price": calculation.close_price,
        "calculated_profit": calculation.calculated_profit,
        "success": calculation.success,
        "error_code": calculation.error_code,
        "observed_at": calculation.observed_at,
    }


def _margin_calculation_interchange(calculation: BrokerMarginCalculation) -> dict[str, Any]:
    return {
        "symbol": calculation.symbol,
        "side": calculation.side,
        "volume": calculation.volume,
        "price": calculation.price,
        "calculated_margin": calculation.calculated_margin,
        "success": calculation.success,
        "error_code": calculation.error_code,
        "observed_at": calculation.observed_at,
    }


_ORDER_MODE_BITS = {
    OrderMode.MARKET: 1,
    OrderMode.LIMIT: 2,
    OrderMode.STOP: 4,
    OrderMode.STOP_LIMIT: 8,
    OrderMode.STOP_LOSS: 16,
    OrderMode.TAKE_PROFIT: 32,
    OrderMode.CLOSE_BY: 64,
}
_FILLING_MODE_BITS = {
    FillingMode.FOK: 1,
    FillingMode.IOC: 2,
    FillingMode.BOC: 4,
}
_EXPIRATION_MODE_BITS = {
    ExpirationMode.GTC: 1,
    ExpirationMode.DAY: 2,
    ExpirationMode.SPECIFIED: 4,
    ExpirationMode.SPECIFIED_DAY: 8,
}


def _mode_mask(values: frozenset[Any], mapping: dict[Any, int]) -> int:
    mask = 0
    for value in values:
        mask |= mapping[value]
    return mask
