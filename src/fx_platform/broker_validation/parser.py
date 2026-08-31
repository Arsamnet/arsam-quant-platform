"""Strict parser for the versioned read-only MT5 JSON interchange contract."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from fx_platform.broker_validation.models import (
    BROKER_SNAPSHOT_SCHEMA_VERSION,
    READ_ONLY_MODE,
    AccountPositionMode,
    AccountTradeMode,
    BrokerAccountSnapshot,
    BrokerContractSnapshot,
    BrokerMarginCalculation,
    BrokerProfitCalculation,
    BrokerSymbolSnapshot,
    BrokerTerminalSnapshot,
    CalculationMode,
    CalculationSide,
    ExpirationMode,
    FillingMode,
    OrderMode,
    SnapshotSourceType,
    SwapMode,
    SymbolTradeMode,
)

MAX_SNAPSHOT_BYTES = 1_000_000


class BrokerSnapshotParseError(ValueError):
    """The snapshot cannot be trusted or normalized under schema 1.0."""


_ACCOUNT_TRADE_MODES = {
    0: AccountTradeMode.DEMO,
    1: AccountTradeMode.CONTEST,
    2: AccountTradeMode.REAL,
}
_ACCOUNT_POSITION_MODES = {
    0: AccountPositionMode.RETAIL_NETTING,
    1: AccountPositionMode.EXCHANGE,
    2: AccountPositionMode.RETAIL_HEDGING,
}
_SYMBOL_TRADE_MODES = {
    0: SymbolTradeMode.DISABLED,
    1: SymbolTradeMode.LONG_ONLY,
    2: SymbolTradeMode.SHORT_ONLY,
    3: SymbolTradeMode.CLOSE_ONLY,
    4: SymbolTradeMode.FULL,
}
_CALCULATION_MODES = {
    0: CalculationMode.FOREX,
    1: CalculationMode.FOREX_NO_LEVERAGE,
    2: CalculationMode.FUTURES,
    3: CalculationMode.CFD,
    4: CalculationMode.CFD_INDEX,
    5: CalculationMode.CFD_LEVERAGE,
    32: CalculationMode.EXCHANGE_STOCKS,
    33: CalculationMode.EXCHANGE_FUTURES,
    34: CalculationMode.EXCHANGE_FUTURES_FORTS,
    35: CalculationMode.EXCHANGE_BONDS,
    36: CalculationMode.EXCHANGE_STOCKS_MOEX,
    37: CalculationMode.EXCHANGE_BONDS_MOEX,
    64: CalculationMode.SERVICE_COLLATERAL,
}
_SWAP_MODES = {
    0: SwapMode.DISABLED,
    1: SwapMode.POINTS,
    2: SwapMode.SYMBOL_CURRENCY,
    3: SwapMode.MARGIN_CURRENCY,
    4: SwapMode.DEPOSIT_CURRENCY,
    5: SwapMode.INTEREST_CURRENT,
    6: SwapMode.INTEREST_OPEN,
    7: SwapMode.REOPEN_CURRENT,
    8: SwapMode.REOPEN_BID,
}
_ORDER_BITS = {
    1: OrderMode.MARKET,
    2: OrderMode.LIMIT,
    4: OrderMode.STOP,
    8: OrderMode.STOP_LIMIT,
    16: OrderMode.STOP_LOSS,
    32: OrderMode.TAKE_PROFIT,
    64: OrderMode.CLOSE_BY,
}
_FILLING_BITS = {1: FillingMode.FOK, 2: FillingMode.IOC, 4: FillingMode.BOC}
_EXPIRATION_BITS = {
    1: ExpirationMode.GTC,
    2: ExpirationMode.DAY,
    4: ExpirationMode.SPECIFIED,
    8: ExpirationMode.SPECIFIED_DAY,
}

_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "mode",
        "source_type",
        "acquired_at",
        "broker",
        "terminal",
        "account",
        "requested_symbols",
        "symbols",
        "profit_calculations",
        "margin_calculations",
    }
)
_BROKER_FIELDS = frozenset({"company", "server"})
_TERMINAL_FIELDS = frozenset(
    {
        "name",
        "build",
        "version",
        "connected",
        "server_time_raw",
        "server_utc_offset_minutes",
    }
)
_ACCOUNT_FIELDS = frozenset(
    {
        "currency",
        "trade_mode_code",
        "leverage",
        "margin_mode_code",
        "trade_allowed",
        "automated_trading_allowed",
        "account_id_hash",
    }
)
_SYMBOL_FIELDS = frozenset(
    {
        "name",
        "base_currency",
        "quote_currency",
        "profit_currency",
        "margin_currency",
        "digits",
        "point",
        "tick_size",
        "tick_value",
        "tick_value_profit",
        "tick_value_loss",
        "contract_size",
        "volume_min",
        "volume_max",
        "volume_step",
        "volume_limit",
        "bid",
        "ask",
        "reported_spread_points",
        "spread_is_floating",
        "trade_mode_code",
        "order_mode_mask",
        "filling_mode_mask",
        "expiration_mode_mask",
        "stop_level_points",
        "freeze_level_points",
        "calculation_mode_code",
        "swap_mode_code",
        "swap_long",
        "swap_short",
        "rollover_day",
        "margin_initial",
        "margin_maintenance",
        "observed_at",
    }
)
_PROFIT_FIELDS = frozenset(
    {
        "symbol",
        "side",
        "volume",
        "open_price",
        "close_price",
        "calculated_profit",
        "success",
        "error_code",
        "observed_at",
    }
)
_MARGIN_FIELDS = frozenset(
    {
        "symbol",
        "side",
        "volume",
        "price",
        "calculated_margin",
        "success",
        "error_code",
        "observed_at",
    }
)


def load_broker_snapshot(
    path: Path,
    *,
    expected_fingerprint: str | None = None,
) -> BrokerContractSnapshot:
    """Load a bounded UTF-8 file and optionally verify its complete canonical identity."""
    try:
        size = path.stat().st_size
        if size > MAX_SNAPSHOT_BYTES:
            raise BrokerSnapshotParseError("snapshot exceeds the one-megabyte safety limit")
        payload = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise BrokerSnapshotParseError(f"cannot read broker snapshot: {error}") from error
    snapshot = parse_broker_snapshot(payload)
    if expected_fingerprint is not None and snapshot.snapshot_fingerprint != expected_fingerprint:
        raise BrokerSnapshotParseError("snapshot fingerprint does not match trusted expectation")
    return snapshot


def parse_broker_snapshot(payload: str) -> BrokerContractSnapshot:
    """Strictly parse schema 1.0; no financial number is accepted as JSON float."""
    try:
        raw = json.loads(payload, object_pairs_hook=_object_without_duplicates)
    except (json.JSONDecodeError, BrokerSnapshotParseError) as error:
        raise BrokerSnapshotParseError(f"malformed broker snapshot JSON: {error}") from error
    root = _object(raw, "snapshot")
    _exact_fields(root, _TOP_LEVEL_FIELDS, "snapshot")
    if _text(root["schema_version"], "schema_version") != BROKER_SNAPSHOT_SCHEMA_VERSION:
        raise BrokerSnapshotParseError("unsupported broker snapshot schema version")
    if _text(root["mode"], "mode") != READ_ONLY_MODE:
        raise BrokerSnapshotParseError("snapshot safety mode is not read_only_metadata_probe")
    try:
        source_type = SnapshotSourceType(_text(root["source_type"], "source_type"))
    except ValueError as error:
        raise BrokerSnapshotParseError("unknown snapshot source_type") from error

    broker = _object(root["broker"], "broker")
    terminal = _object(root["terminal"], "terminal")
    account = _object(root["account"], "account")
    _exact_fields(broker, _BROKER_FIELDS, "broker")
    _exact_fields(terminal, _TERMINAL_FIELDS, "terminal")
    _exact_fields(account, _ACCOUNT_FIELDS, "account")

    trade_mode_code = _integer(account["trade_mode_code"], "account.trade_mode_code")
    margin_mode_code = _integer(account["margin_mode_code"], "account.margin_mode_code")
    symbols = tuple(
        _parse_symbol(item, index) for index, item in enumerate(_array(root["symbols"], "symbols"))
    )
    profits = tuple(
        _parse_profit(item, index)
        for index, item in enumerate(_array(root["profit_calculations"], "profit_calculations"))
    )
    margins = tuple(
        _parse_margin(item, index)
        for index, item in enumerate(_array(root["margin_calculations"], "margin_calculations"))
    )
    requested_symbols = tuple(
        _text(value, f"requested_symbols[{index}]")
        for index, value in enumerate(_array(root["requested_symbols"], "requested_symbols"))
    )
    try:
        return BrokerContractSnapshot(
            schema_version=BROKER_SNAPSHOT_SCHEMA_VERSION,
            mode=READ_ONLY_MODE,
            source_type=source_type,
            acquired_at=_timestamp(root["acquired_at"], "acquired_at"),
            broker_company=_text(broker["company"], "broker.company"),
            broker_server=_text(broker["server"], "broker.server"),
            terminal=BrokerTerminalSnapshot(
                name=_text(terminal["name"], "terminal.name"),
                build=_integer(terminal["build"], "terminal.build"),
                version=_nullable_text(terminal["version"], "terminal.version"),
                connected=_boolean(terminal["connected"], "terminal.connected"),
                server_time_raw=_nullable_text(
                    terminal["server_time_raw"], "terminal.server_time_raw"
                ),
                server_utc_offset_minutes=_nullable_integer(
                    terminal["server_utc_offset_minutes"],
                    "terminal.server_utc_offset_minutes",
                ),
            ),
            account=BrokerAccountSnapshot(
                currency=_text(account["currency"], "account.currency"),
                trade_mode=_ACCOUNT_TRADE_MODES.get(trade_mode_code, AccountTradeMode.UNKNOWN),
                trade_mode_code=trade_mode_code,
                leverage=_integer(account["leverage"], "account.leverage"),
                position_mode=_ACCOUNT_POSITION_MODES.get(
                    margin_mode_code, AccountPositionMode.UNKNOWN
                ),
                margin_mode_code=margin_mode_code,
                trade_allowed=_boolean(account["trade_allowed"], "account.trade_allowed"),
                automated_trading_allowed=_boolean(
                    account["automated_trading_allowed"],
                    "account.automated_trading_allowed",
                ),
                account_id_hash=_nullable_text(
                    account["account_id_hash"], "account.account_id_hash"
                ),
            ),
            requested_symbols=requested_symbols,
            symbols=symbols,
            profit_calculations=profits,
            margin_calculations=margins,
        )
    except ValueError as error:
        raise BrokerSnapshotParseError(str(error)) from error


def decode_order_modes(mask: int) -> tuple[frozenset[OrderMode], int]:
    """Decode known order bits and return unknown bits without discarding them."""
    return _decode_mask(mask, _ORDER_BITS, "order mode")


def decode_filling_modes(mask: int) -> tuple[frozenset[FillingMode], int]:
    """Decode known filling bits and return unknown bits without discarding them."""
    return _decode_mask(mask, _FILLING_BITS, "filling mode")


def decode_expiration_modes(mask: int) -> tuple[frozenset[ExpirationMode], int]:
    """Decode known expiration bits and return unknown bits without discarding them."""
    return _decode_mask(mask, _EXPIRATION_BITS, "expiration mode")


def _parse_symbol(value: Any, index: int) -> BrokerSymbolSnapshot:
    field = f"symbols[{index}]"
    item = _object(value, field)
    _exact_fields(item, _SYMBOL_FIELDS, field)
    trade_mode_code = _integer(item["trade_mode_code"], f"{field}.trade_mode_code")
    calculation_mode_code = _integer(
        item["calculation_mode_code"], f"{field}.calculation_mode_code"
    )
    swap_mode_code = _integer(item["swap_mode_code"], f"{field}.swap_mode_code")
    order_modes, order_unknown = decode_order_modes(
        _integer(item["order_mode_mask"], f"{field}.order_mode_mask")
    )
    filling_modes, filling_unknown = decode_filling_modes(
        _integer(item["filling_mode_mask"], f"{field}.filling_mode_mask")
    )
    expiration_modes, expiration_unknown = decode_expiration_modes(
        _integer(item["expiration_mode_mask"], f"{field}.expiration_mode_mask")
    )
    try:
        return BrokerSymbolSnapshot(
            name=_text(item["name"], f"{field}.name"),
            base_currency=_text(item["base_currency"], f"{field}.base_currency"),
            quote_currency=_text(item["quote_currency"], f"{field}.quote_currency"),
            profit_currency=_text(item["profit_currency"], f"{field}.profit_currency"),
            margin_currency=_text(item["margin_currency"], f"{field}.margin_currency"),
            digits=_integer(item["digits"], f"{field}.digits"),
            point=_decimal(item["point"], f"{field}.point"),
            tick_size=_decimal(item["tick_size"], f"{field}.tick_size"),
            tick_value=_decimal(item["tick_value"], f"{field}.tick_value"),
            tick_value_profit=_decimal(item["tick_value_profit"], f"{field}.tick_value_profit"),
            tick_value_loss=_decimal(item["tick_value_loss"], f"{field}.tick_value_loss"),
            contract_size=_decimal(item["contract_size"], f"{field}.contract_size"),
            volume_min=_decimal(item["volume_min"], f"{field}.volume_min"),
            volume_max=_decimal(item["volume_max"], f"{field}.volume_max"),
            volume_step=_decimal(item["volume_step"], f"{field}.volume_step"),
            volume_limit=_decimal(item["volume_limit"], f"{field}.volume_limit"),
            bid=_decimal(item["bid"], f"{field}.bid"),
            ask=_decimal(item["ask"], f"{field}.ask"),
            reported_spread_points=_integer(
                item["reported_spread_points"], f"{field}.reported_spread_points"
            ),
            spread_is_floating=_boolean(item["spread_is_floating"], f"{field}.spread_is_floating"),
            trade_mode=_SYMBOL_TRADE_MODES.get(trade_mode_code, SymbolTradeMode.UNKNOWN),
            trade_mode_code=trade_mode_code,
            order_modes=order_modes,
            order_mode_unknown_bits=order_unknown,
            filling_modes=filling_modes,
            filling_mode_unknown_bits=filling_unknown,
            expiration_modes=expiration_modes,
            expiration_mode_unknown_bits=expiration_unknown,
            stop_level_points=_integer(item["stop_level_points"], f"{field}.stop_level_points"),
            freeze_level_points=_integer(
                item["freeze_level_points"], f"{field}.freeze_level_points"
            ),
            calculation_mode=_CALCULATION_MODES.get(calculation_mode_code, CalculationMode.UNKNOWN),
            calculation_mode_code=calculation_mode_code,
            swap_mode=_SWAP_MODES.get(swap_mode_code, SwapMode.UNKNOWN),
            swap_mode_code=swap_mode_code,
            swap_long=_decimal(item["swap_long"], f"{field}.swap_long"),
            swap_short=_decimal(item["swap_short"], f"{field}.swap_short"),
            rollover_day=_integer(item["rollover_day"], f"{field}.rollover_day"),
            margin_initial=_decimal(item["margin_initial"], f"{field}.margin_initial"),
            margin_maintenance=_decimal(item["margin_maintenance"], f"{field}.margin_maintenance"),
            observed_at=_timestamp(item["observed_at"], f"{field}.observed_at"),
        )
    except ValueError as error:
        raise BrokerSnapshotParseError(f"{field}: {error}") from error


def _parse_profit(value: Any, index: int) -> BrokerProfitCalculation:
    field = f"profit_calculations[{index}]"
    item = _object(value, field)
    _exact_fields(item, _PROFIT_FIELDS, field)
    try:
        side = CalculationSide(_text(item["side"], f"{field}.side"))
    except ValueError as error:
        raise BrokerSnapshotParseError(f"{field}.side is an unknown enum") from error
    try:
        return BrokerProfitCalculation(
            symbol=_text(item["symbol"], f"{field}.symbol"),
            side=side,
            volume=_decimal(item["volume"], f"{field}.volume"),
            open_price=_decimal(item["open_price"], f"{field}.open_price"),
            close_price=_decimal(item["close_price"], f"{field}.close_price"),
            calculated_profit=_nullable_decimal(
                item["calculated_profit"], f"{field}.calculated_profit"
            ),
            success=_boolean(item["success"], f"{field}.success"),
            error_code=_integer(item["error_code"], f"{field}.error_code"),
            observed_at=_timestamp(item["observed_at"], f"{field}.observed_at"),
        )
    except ValueError as error:
        raise BrokerSnapshotParseError(f"{field}: {error}") from error


def _parse_margin(value: Any, index: int) -> BrokerMarginCalculation:
    field = f"margin_calculations[{index}]"
    item = _object(value, field)
    _exact_fields(item, _MARGIN_FIELDS, field)
    try:
        side = CalculationSide(_text(item["side"], f"{field}.side"))
    except ValueError as error:
        raise BrokerSnapshotParseError(f"{field}.side is an unknown enum") from error
    try:
        return BrokerMarginCalculation(
            symbol=_text(item["symbol"], f"{field}.symbol"),
            side=side,
            volume=_decimal(item["volume"], f"{field}.volume"),
            price=_decimal(item["price"], f"{field}.price"),
            calculated_margin=_nullable_decimal(
                item["calculated_margin"], f"{field}.calculated_margin"
            ),
            success=_boolean(item["success"], f"{field}.success"),
            error_code=_integer(item["error_code"], f"{field}.error_code"),
            observed_at=_timestamp(item["observed_at"], f"{field}.observed_at"),
        )
    except ValueError as error:
        raise BrokerSnapshotParseError(f"{field}: {error}") from error


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BrokerSnapshotParseError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise BrokerSnapshotParseError(f"{field} must be an object")
    return cast("dict[str, Any]", value)


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise BrokerSnapshotParseError(f"{field} must be an array")
    return value


def _exact_fields(value: Mapping[str, Any], expected: frozenset[str], field: str) -> None:
    actual = frozenset(value)
    missing = expected - actual
    extra = actual - expected
    if missing:
        raise BrokerSnapshotParseError(f"{field} is missing fields: {', '.join(sorted(missing))}")
    if extra:
        raise BrokerSnapshotParseError(f"{field} has unknown fields: {', '.join(sorted(extra))}")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise BrokerSnapshotParseError(f"{field} must be non-empty text")
    return str(value)


def _nullable_text(value: Any, field: str) -> str | None:
    return None if value is None else _text(value, field)


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BrokerSnapshotParseError(f"{field} must be an integer")
    if value < 0:
        raise BrokerSnapshotParseError(f"{field} must not be negative")
    return int(value)


def _nullable_integer(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise BrokerSnapshotParseError(f"{field} must be an integer or null")
    return int(value)


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise BrokerSnapshotParseError(f"{field} must be a boolean")
    return value


def _decimal(value: Any, field: str) -> Decimal:
    if not isinstance(value, str) or not value:
        raise BrokerSnapshotParseError(f"{field} must be a decimal string")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise BrokerSnapshotParseError(f"{field} is a malformed decimal") from error
    if not result.is_finite():
        raise BrokerSnapshotParseError(f"{field} must be finite")
    return result


def _nullable_decimal(value: Any, field: str) -> Decimal | None:
    return None if value is None else _decimal(value, field)


def _timestamp(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        result = datetime.fromisoformat(text)
    except ValueError as error:
        raise BrokerSnapshotParseError(f"{field} is an invalid timestamp") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise BrokerSnapshotParseError(f"{field} must include a UTC offset")
    return result.astimezone(UTC)


def _decode_mask[EnumT](
    mask: int,
    mapping: Mapping[int, EnumT],
    field: str,
) -> tuple[frozenset[EnumT], int]:
    if isinstance(mask, bool) or not isinstance(mask, int) or mask < 0:
        raise BrokerSnapshotParseError(f"{field} mask must be a non-negative integer")
    known_mask = 0
    values: set[EnumT] = set()
    for bit, value in mapping.items():
        known_mask |= bit
        if mask & bit:
            values.add(value)
    return frozenset(values), mask & ~known_mask
