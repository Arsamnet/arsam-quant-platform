"""Deterministic, fail-closed broker contract and calculation validation."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from fx_platform import __version__
from fx_platform.broker_validation.models import (
    BROKER_REPORT_SCHEMA_VERSION,
    AccountPositionMode,
    AccountTradeMode,
    BrokerContractSnapshot,
    BrokerProfitCalculation,
    BrokerReadiness,
    BrokerSymbolSnapshot,
    BrokerValidationCheck,
    BrokerValidationReport,
    CalculationMode,
    CalculationSide,
    OrderMode,
    SymbolTradeMode,
    ValidationOverallStatus,
    ValidationSeverity,
)
from fx_platform.domain.common import require_finite_decimal, require_utc
from fx_platform.domain.market import SymbolSpecification
from fx_platform.serialization import fingerprint

_CURRENCY_CODE_LENGTH = 3
_EXPECTED_PERMISSION = True


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationPolicy:
    """Explicit, fingerprinted tolerance and future-readiness expectations."""

    expected_account_currency: str = "USD"
    expected_account_trade_mode: AccountTradeMode = AccountTradeMode.DEMO
    expected_position_mode: AccountPositionMode = AccountPositionMode.RETAIL_HEDGING
    expected_broker_company: str | None = None
    expected_broker_server: str | None = None
    supported_calculation_modes: frozenset[CalculationMode] = frozenset(
        {CalculationMode.FOREX, CalculationMode.FOREX_NO_LEVERAGE}
    )
    maximum_snapshot_age: timedelta = timedelta(minutes=5)
    maximum_future_skew: timedelta = timedelta(seconds=2)
    absolute_money_tolerance: Decimal = Decimal("0.01")
    relative_money_tolerance: Decimal = Decimal("0.0001")
    price_tolerance_ticks: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if (
            len(self.expected_account_currency) != _CURRENCY_CODE_LENGTH
            or self.expected_account_currency != self.expected_account_currency.upper()
        ):
            raise ValueError("expected account currency must be uppercase ISO-style text")
        if not self.supported_calculation_modes:
            raise ValueError("at least one calculation mode must be supported")
        for field_name, identity_value in (
            ("expected_broker_company", self.expected_broker_company),
            ("expected_broker_server", self.expected_broker_server),
        ):
            if identity_value is not None and not identity_value:
                raise ValueError(f"{field_name} must not be empty when configured")
        for field_name, duration in (
            ("maximum_snapshot_age", self.maximum_snapshot_age),
            ("maximum_future_skew", self.maximum_future_skew),
        ):
            if duration < timedelta(0):
                raise ValueError(f"{field_name} must not be negative")
        for field_name, decimal_value in (
            ("absolute_money_tolerance", self.absolute_money_tolerance),
            ("relative_money_tolerance", self.relative_money_tolerance),
            ("price_tolerance_ticks", self.price_tolerance_ticks),
        ):
            require_finite_decimal(decimal_value, field_name)
            if decimal_value < Decimal(0):
                raise ValueError(f"{field_name} must not be negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_account_currency": self.expected_account_currency,
            "expected_account_trade_mode": self.expected_account_trade_mode,
            "expected_position_mode": self.expected_position_mode,
            "expected_broker_company": self.expected_broker_company,
            "expected_broker_server": self.expected_broker_server,
            "supported_calculation_modes": self.supported_calculation_modes,
            "maximum_snapshot_age": self.maximum_snapshot_age,
            "maximum_future_skew": self.maximum_future_skew,
            "absolute_money_tolerance": self.absolute_money_tolerance,
            "relative_money_tolerance": self.relative_money_tolerance,
            "price_tolerance_ticks": self.price_tolerance_ticks,
        }

    @property
    def policy_fingerprint(self) -> str:
        return fingerprint(self.to_dict())


class BrokerContractValidator:
    """Compare one expected platform symbol against authoritative broker evidence."""

    def validate(
        self,
        *,
        expected: SymbolSpecification,
        snapshot: BrokerContractSnapshot,
        symbol: str,
        policy: ValidationPolicy,
        as_of: datetime,
    ) -> BrokerValidationReport:
        """Return every applicable check; uncertainty becomes a blocking result."""
        require_utc(as_of, "as_of")
        if expected.symbol != symbol:
            raise ValueError("expected specification symbol does not match validation symbol")
        checks: list[BrokerValidationCheck] = []
        self._check_snapshot_context(checks, snapshot, policy, as_of)
        broker_symbol = snapshot.symbol(symbol)
        if broker_symbol is None:
            self._add(
                checks,
                "symbol_unavailable",
                "symbol.name",
                ValidationSeverity.BLOCKING,
                symbol,
                None,
                "Requested symbol was not present in the broker snapshot.",
            )
        else:
            self._add(
                checks,
                "symbol_available",
                "symbol.name",
                ValidationSeverity.PASS,
                symbol,
                broker_symbol.name,
                "Requested symbol is present without alias guessing.",
            )
            self._check_symbol_contract(checks, expected, broker_symbol, policy)
            self._check_dynamic_observation(checks, expected, broker_symbol, policy, as_of)
            self._check_calibrations(checks, snapshot, broker_symbol, policy)

        overall = self._overall_status(checks)
        readiness = (
            BrokerReadiness.UNKNOWN
            if broker_symbol is None
            else (
                BrokerReadiness.NOT_READY
                if overall is ValidationOverallStatus.BLOCKING_MISMATCH
                else BrokerReadiness.READY
            )
        )
        return BrokerValidationReport(
            schema_version=BROKER_REPORT_SCHEMA_VERSION,
            snapshot_fingerprint=snapshot.snapshot_fingerprint,
            contract_fingerprint=snapshot.contract_fingerprint,
            policy_fingerprint=policy.policy_fingerprint,
            platform_version=__version__,
            symbol=symbol,
            account_currency=snapshot.account.currency,
            validated_at=as_of,
            validation_time_semantics="explicit_as_of_utc",
            overall_status=overall,
            readiness=readiness,
            checks=tuple(checks),
        )

    def _check_snapshot_context(
        self,
        checks: list[BrokerValidationCheck],
        snapshot: BrokerContractSnapshot,
        policy: ValidationPolicy,
        as_of: datetime,
    ) -> None:
        if snapshot.acquired_at - as_of > policy.maximum_future_skew:
            self._add(
                checks,
                "snapshot_from_future",
                "acquired_at",
                ValidationSeverity.BLOCKING,
                f"<= {as_of.isoformat()}",
                snapshot.acquired_at,
                "Snapshot acquisition is beyond the permitted future skew.",
            )
        elif as_of - snapshot.acquired_at > policy.maximum_snapshot_age:
            self._add(
                checks,
                "snapshot_stale",
                "acquired_at",
                ValidationSeverity.BLOCKING,
                policy.maximum_snapshot_age,
                as_of - snapshot.acquired_at,
                "Dynamic evidence is too old for current readiness.",
            )
        else:
            self._add(
                checks,
                "snapshot_fresh",
                "acquired_at",
                ValidationSeverity.PASS,
                policy.maximum_snapshot_age,
                max(as_of - snapshot.acquired_at, timedelta(0)),
                "Snapshot is within the explicit freshness window.",
            )
        self._optional_identity(
            checks,
            code="broker_company",
            field="broker.company",
            expected=policy.expected_broker_company,
            observed=snapshot.broker_company,
        )
        self._optional_identity(
            checks,
            code="broker_server",
            field="broker.server",
            expected=policy.expected_broker_server,
            observed=snapshot.broker_server,
        )
        self._add(
            checks,
            "terminal_build_captured",
            "terminal.build",
            ValidationSeverity.INFO,
            "captured and contract-fingerprinted",
            snapshot.terminal.build,
            "Terminal build changes are visible in contract diff and fingerprint.",
        )
        self._equality(
            checks,
            code="account_currency",
            field="account.currency",
            expected=policy.expected_account_currency,
            observed=snapshot.account.currency,
            mismatch=ValidationSeverity.BLOCKING,
            mismatch_message="Account currency differs from configured platform risk currency.",
        )
        self._equality(
            checks,
            code="account_trade_mode",
            field="account.trade_mode",
            expected=policy.expected_account_trade_mode,
            observed=snapshot.account.trade_mode,
            mismatch=ValidationSeverity.BLOCKING,
            mismatch_message="Account is not the expected demo environment.",
        )
        self._equality(
            checks,
            code="account_position_mode",
            field="account.position_mode",
            expected=policy.expected_position_mode,
            observed=snapshot.account.position_mode,
            mismatch=ValidationSeverity.BLOCKING,
            mismatch_message="Account hedging/netting mode is incompatible with node assumptions.",
        )
        self._boolean_required(
            checks,
            "terminal_connected",
            "terminal.connected",
            snapshot.terminal.connected,
            "Terminal was not connected while metadata was acquired.",
        )
        self._boolean_required(
            checks,
            "account_trade_allowed",
            "account.trade_allowed",
            snapshot.account.trade_allowed,
            "Account did not permit trading at acquisition time.",
        )
        self._boolean_required(
            checks,
            "account_automated_trading_allowed",
            "account.automated_trading_allowed",
            snapshot.account.automated_trading_allowed,
            "Account did not permit automated trading at acquisition time.",
        )
        if snapshot.terminal.server_utc_offset_minutes is None:
            self._add(
                checks,
                "server_timezone_unknown",
                "terminal.server_utc_offset_minutes",
                ValidationSeverity.INFO,
                "explicit offset or unknown",
                None,
                "Raw server time is retained but is not falsely labelled UTC.",
            )

    def _check_symbol_contract(
        self,
        checks: list[BrokerValidationCheck],
        expected: SymbolSpecification,
        observed: BrokerSymbolSnapshot,
        policy: ValidationPolicy,
    ) -> None:
        self._equality(
            checks,
            "symbol_trade_mode",
            "symbol.trade_mode",
            SymbolTradeMode.FULL,
            observed.trade_mode,
            ValidationSeverity.BLOCKING,
            "Symbol is not fully trade-enabled.",
        )
        calculation_supported = observed.calculation_mode in policy.supported_calculation_modes
        self._add(
            checks,
            "calculation_mode_supported",
            "symbol.calculation_mode",
            ValidationSeverity.PASS if calculation_supported else ValidationSeverity.BLOCKING,
            policy.supported_calculation_modes,
            observed.calculation_mode,
            (
                "Calculation mode is supported by the current FX mapping."
                if calculation_supported
                else (
                    "Calculation mode is unknown or unsupported; future execution must fail closed."
                )
            ),
        )
        for code, field, expected_value, observed_value in (
            (
                "base_currency",
                "symbol.base_currency",
                expected.base_currency,
                observed.base_currency,
            ),
            (
                "quote_currency",
                "symbol.quote_currency",
                expected.quote_currency,
                observed.quote_currency,
            ),
            (
                "profit_currency",
                "symbol.profit_currency",
                expected.tick_value_currency,
                observed.profit_currency,
            ),
            (
                "contract_size",
                "symbol.contract_size",
                expected.contract_size,
                observed.contract_size,
            ),
            ("tick_size", "symbol.tick_size", expected.tick_size, observed.tick_size),
            ("price_digits", "symbol.digits", expected.price_digits, observed.digits),
            ("volume_step", "symbol.volume_step", expected.volume_step, observed.volume_step),
        ):
            self._equality(
                checks,
                code,
                field,
                expected_value,
                observed_value,
                ValidationSeverity.BLOCKING,
                f"Broker {field} is incompatible with the platform specification.",
            )

        self._volume_bounds(checks, expected, observed)
        expected_point = Decimal(1).scaleb(-observed.digits)
        self._equality(
            checks,
            "point_digits_relation",
            "symbol.point",
            expected_point,
            observed.point,
            ValidationSeverity.BLOCKING,
            "Broker point does not equal 10 raised to minus digits.",
        )
        tick_aligned = observed.point > 0 and observed.tick_size % observed.point == Decimal(0)
        self._add(
            checks,
            "tick_size_point_grid",
            "symbol.tick_size",
            ValidationSeverity.PASS if tick_aligned else ValidationSeverity.BLOCKING,
            "integer multiple of point",
            observed.tick_size,
            (
                "Tick size is aligned to the point grid."
                if tick_aligned
                else "Tick size is not aligned to the point grid."
            ),
        )
        for code, field, value in (
            ("contract_size_positive", "symbol.contract_size", observed.contract_size),
            ("tick_size_positive", "symbol.tick_size", observed.tick_size),
            ("tick_value_positive", "symbol.tick_value", observed.tick_value),
            ("volume_min_positive", "symbol.volume_min", observed.volume_min),
            ("volume_max_positive", "symbol.volume_max", observed.volume_max),
            ("volume_step_positive", "symbol.volume_step", observed.volume_step),
        ):
            positive = value > Decimal(0)
            self._add(
                checks,
                code,
                field,
                ValidationSeverity.PASS if positive else ValidationSeverity.BLOCKING,
                "> 0",
                value,
                "Required financial metadata is positive."
                if positive
                else "Required financial metadata is unusable.",
            )
        volume_range_valid = observed.volume_max >= observed.volume_min
        self._add(
            checks,
            "volume_range",
            "symbol.volume_min/volume_max",
            ValidationSeverity.PASS if volume_range_valid else ValidationSeverity.BLOCKING,
            "volume_min <= volume_max",
            {"min": observed.volume_min, "max": observed.volume_max},
            "Broker volume range is ordered."
            if volume_range_valid
            else "Broker volume range is inverted.",
        )
        self._mode_bits(checks, observed)
        self._add(
            checks,
            "stop_freeze_levels_captured",
            "symbol.stop_level_points/freeze_level_points",
            ValidationSeverity.INFO,
            "captured non-negative points",
            {"stop": observed.stop_level_points, "freeze": observed.freeze_level_points},
            "Levels are evidence for a future final execution guard; no order behavior "
            "changes here.",
        )

    def _volume_bounds(
        self,
        checks: list[BrokerValidationCheck],
        expected: SymbolSpecification,
        observed: BrokerSymbolSnapshot,
    ) -> None:
        if observed.volume_min > expected.volume_min:
            minimum_severity = ValidationSeverity.BLOCKING
            minimum_message = "Platform minimum can request volume below the broker minimum."
        elif observed.volume_min < expected.volume_min:
            minimum_severity = ValidationSeverity.WARNING
            minimum_message = "Platform minimum is more conservative than the broker minimum."
        else:
            minimum_severity = ValidationSeverity.PASS
            minimum_message = "Platform and broker minimum volume agree."
        self._add(
            checks,
            "volume_minimum",
            "symbol.volume_min",
            minimum_severity,
            expected.volume_min,
            observed.volume_min,
            minimum_message,
        )
        if observed.volume_max < expected.volume_max:
            maximum_severity = ValidationSeverity.BLOCKING
            maximum_message = "Platform maximum exceeds the broker per-order maximum."
        elif observed.volume_max > expected.volume_max:
            maximum_severity = ValidationSeverity.INFO
            maximum_message = "Platform maximum is more conservative than the broker maximum."
        else:
            maximum_severity = ValidationSeverity.PASS
            maximum_message = "Platform and broker maximum volume agree."
        self._add(
            checks,
            "volume_maximum",
            "symbol.volume_max",
            maximum_severity,
            expected.volume_max,
            observed.volume_max,
            maximum_message,
        )
        limit_compatible = (
            observed.volume_limit == 0 or observed.volume_limit >= expected.volume_max
        )
        self._add(
            checks,
            "volume_limit",
            "symbol.volume_limit",
            ValidationSeverity.PASS if limit_compatible else ValidationSeverity.BLOCKING,
            f"0 or >= {expected.volume_max}",
            observed.volume_limit,
            (
                "Broker aggregate directional limit does not undercut the platform maximum."
                if limit_compatible
                else "Broker aggregate directional limit is below the platform maximum."
            ),
        )

    def _mode_bits(
        self,
        checks: list[BrokerValidationCheck],
        observed: BrokerSymbolSnapshot,
    ) -> None:
        market_allowed = OrderMode.MARKET in observed.order_modes
        self._add(
            checks,
            "market_order_mode",
            "symbol.order_modes",
            ValidationSeverity.PASS if market_allowed else ValidationSeverity.BLOCKING,
            OrderMode.MARKET,
            observed.order_modes,
            "Market order mode is available."
            if market_allowed
            else "Market order mode is unavailable.",
        )
        filling_known = bool(observed.filling_modes)
        self._add(
            checks,
            "filling_mode_available",
            "symbol.filling_modes",
            ValidationSeverity.PASS if filling_known else ValidationSeverity.BLOCKING,
            "at least one explicit mode",
            observed.filling_modes,
            "Filling modes are explicit."
            if filling_known
            else "No supported filling mode was observed.",
        )
        for code, field, unknown_bits in (
            (
                "unknown_order_mode_bits",
                "symbol.order_mode_unknown_bits",
                observed.order_mode_unknown_bits,
            ),
            (
                "unknown_filling_mode_bits",
                "symbol.filling_mode_unknown_bits",
                observed.filling_mode_unknown_bits,
            ),
            (
                "unknown_expiration_mode_bits",
                "symbol.expiration_mode_unknown_bits",
                observed.expiration_mode_unknown_bits,
            ),
        ):
            self._add(
                checks,
                code,
                field,
                ValidationSeverity.PASS if unknown_bits == 0 else ValidationSeverity.BLOCKING,
                0,
                unknown_bits,
                "No unknown capability bits."
                if unknown_bits == 0
                else "Unknown capability bits cannot be ignored safely.",
            )

    def _check_dynamic_observation(
        self,
        checks: list[BrokerValidationCheck],
        expected: SymbolSpecification,
        observed: BrokerSymbolSnapshot,
        policy: ValidationPolicy,
        as_of: datetime,
    ) -> None:
        if observed.observed_at - as_of > policy.maximum_future_skew:
            observation_severity = ValidationSeverity.BLOCKING
            observation_code = "symbol_observation_from_future"
            observation_message = "Symbol observation is beyond the permitted future skew."
        elif as_of - observed.observed_at > policy.maximum_snapshot_age:
            observation_severity = ValidationSeverity.BLOCKING
            observation_code = "symbol_observation_stale"
            observation_message = "Dynamic symbol observation is too old for current readiness."
        else:
            observation_severity = ValidationSeverity.PASS
            observation_code = "symbol_observation_fresh"
            observation_message = "Symbol observation is within the explicit freshness window."
        self._add(
            checks,
            observation_code,
            "symbol.observed_at",
            observation_severity,
            policy.maximum_snapshot_age,
            observed.observed_at,
            observation_message,
        )
        quote_valid = observed.bid > 0 and observed.ask >= observed.bid
        self._add(
            checks,
            "quote_order",
            "symbol.bid/ask",
            ValidationSeverity.PASS if quote_valid else ValidationSeverity.BLOCKING,
            "ask >= bid > 0",
            {"bid": observed.bid, "ask": observed.ask},
            "Observed quote is ordered." if quote_valid else "Observed quote is invalid.",
        )
        spread_difference = abs(observed.observed_spread - observed.reported_spread)
        spread_tolerance = observed.tick_size * policy.price_tolerance_ticks
        spread_consistent = spread_difference <= spread_tolerance
        self._add(
            checks,
            "spread_consistency",
            "symbol.reported_spread_points",
            ValidationSeverity.PASS if spread_consistent else ValidationSeverity.WARNING,
            observed.observed_spread,
            observed.reported_spread,
            (
                "Reported spread agrees with the Bid/Ask observation."
                if spread_consistent
                else "Reported point spread differs from Ask minus Bid within point/tick semantics."
            ),
        )
        maximum_spread = expected.maximum_spread
        if maximum_spread is None:
            self._add(
                checks,
                "spread_policy_unavailable",
                "expected.max_spread_ticks",
                ValidationSeverity.BLOCKING,
                "configured",
                None,
                "Platform spread policy is unavailable.",
            )
        else:
            spread_ok = observed.observed_spread <= maximum_spread
            self._add(
                checks,
                "observed_spread",
                "symbol.ask-bid",
                ValidationSeverity.PASS if spread_ok else ValidationSeverity.WARNING,
                f"<= {maximum_spread}",
                observed.observed_spread,
                (
                    "Observed spread is within the static platform policy."
                    if spread_ok
                    else (
                        "One dynamic spread observation exceeded policy; it is not a permanent "
                        "contract fact."
                    )
                ),
            )
        for code, field, broker_value in (
            ("tick_value", "symbol.tick_value", observed.tick_value),
            ("tick_value_profit", "symbol.tick_value_profit", observed.tick_value_profit),
            ("tick_value_loss", "symbol.tick_value_loss", observed.tick_value_loss),
        ):
            close = self._money_close(expected.tick_value, broker_value, policy)
            self._add(
                checks,
                code,
                field,
                ValidationSeverity.PASS if close else ValidationSeverity.WARNING,
                expected.tick_value,
                broker_value,
                (
                    "Observed dynamic tick value is within explicit tolerance."
                    if close
                    else "Observed dynamic tick value differs; broker equivalence is not claimed."
                ),
            )

    def _check_calibrations(
        self,
        checks: list[BrokerValidationCheck],
        snapshot: BrokerContractSnapshot,
        symbol: BrokerSymbolSnapshot,
        policy: ValidationPolicy,
    ) -> None:
        cases = tuple(
            calculation
            for calculation in snapshot.profit_calculations
            if calculation.symbol == symbol.name
        )
        if not cases:
            self._add(
                checks,
                "profit_calibration_missing",
                "profit_calculations",
                ValidationSeverity.WARNING,
                "BUY and SELL read-only cases",
                (),
                "No OrderCalcProfit evidence was exported; broker-equivalent P/L is not claimed.",
            )
        for index, calculation in enumerate(cases):
            self._profit_case(checks, symbol, calculation, policy, index)
        margin_cases = tuple(
            calculation
            for calculation in snapshot.margin_calculations
            if calculation.symbol == symbol.name
        )
        self._add(
            checks,
            "margin_calibration_captured",
            "margin_calculations",
            ValidationSeverity.INFO,
            "read-only evidence when available",
            len(margin_cases),
            "OrderCalcMargin evidence is archived but does not alter the current Risk Engine.",
        )

    def _profit_case(
        self,
        checks: list[BrokerValidationCheck],
        symbol: BrokerSymbolSnapshot,
        calculation: BrokerProfitCalculation,
        policy: ValidationPolicy,
        index: int,
    ) -> None:
        field = f"profit_calculations[{index}]"
        if not calculation.success or calculation.calculated_profit is None:
            self._add(
                checks,
                "profit_calculation_failed",
                field,
                ValidationSeverity.WARNING,
                "successful read-only calculation",
                calculation.error_code,
                "MT5 did not return a calibration result.",
            )
            return
        if symbol.profit_currency != policy.expected_account_currency:
            self._add(
                checks,
                "profit_calibration_conversion_required",
                field,
                ValidationSeverity.INFO,
                policy.expected_account_currency,
                symbol.profit_currency,
                "A directed point-in-time conversion is required before comparison.",
            )
            return
        direction = Decimal(1) if calculation.side is CalculationSide.BUY else Decimal(-1)
        platform_profit = (
            direction
            * (calculation.close_price - calculation.open_price)
            * symbol.contract_size
            * calculation.volume
        )
        difference = abs(platform_profit - calculation.calculated_profit)
        close = self._money_close(platform_profit, calculation.calculated_profit, policy)
        relative_difference = None if platform_profit == 0 else difference / abs(platform_profit)
        self._add(
            checks,
            "profit_calibration",
            field,
            ValidationSeverity.PASS if close else ValidationSeverity.BLOCKING,
            platform_profit,
            {
                "mt5": calculation.calculated_profit,
                "absolute_difference": difference,
                "relative_difference": relative_difference,
                "absolute_tolerance": policy.absolute_money_tolerance,
                "relative_tolerance": policy.relative_money_tolerance,
            },
            (
                "Platform and read-only MT5 profit calculations agree within tolerance."
                if close
                else "Platform and MT5 profit calculations disagree beyond tolerance."
            ),
        )

    @staticmethod
    def _money_close(expected: Decimal, observed: Decimal, policy: ValidationPolicy) -> bool:
        difference = abs(expected - observed)
        if difference <= policy.absolute_money_tolerance:
            return True
        scale = max(abs(expected), abs(observed))
        return scale > 0 and difference / scale <= policy.relative_money_tolerance

    @staticmethod
    def _overall_status(checks: list[BrokerValidationCheck]) -> ValidationOverallStatus:
        severities = {check.severity for check in checks}
        if ValidationSeverity.BLOCKING in severities:
            return ValidationOverallStatus.BLOCKING_MISMATCH
        if ValidationSeverity.WARNING in severities:
            return ValidationOverallStatus.WARNING
        return ValidationOverallStatus.PASS

    def _equality(  # noqa: PLR0917 - explicit check fields are audit data
        self,
        checks: list[BrokerValidationCheck],
        code: str,
        field: str,
        expected: Any,
        observed: Any,
        mismatch: ValidationSeverity,
        mismatch_message: str,
    ) -> None:
        agrees = expected == observed
        self._add(
            checks,
            code,
            field,
            ValidationSeverity.PASS if agrees else mismatch,
            expected,
            observed,
            "Expected and broker-observed values agree." if agrees else mismatch_message,
        )

    def _boolean_required(
        self,
        checks: list[BrokerValidationCheck],
        code: str,
        field: str,
        observed: bool,
        mismatch_message: str,
    ) -> None:
        self._add(
            checks,
            code,
            field,
            ValidationSeverity.PASS if observed else ValidationSeverity.BLOCKING,
            _EXPECTED_PERMISSION,
            observed,
            "Required point-in-time permission was observed." if observed else mismatch_message,
        )

    def _optional_identity(
        self,
        checks: list[BrokerValidationCheck],
        *,
        code: str,
        field: str,
        expected: str | None,
        observed: str,
    ) -> None:
        if expected is None:
            self._add(
                checks,
                f"{code}_unpinned",
                field,
                ValidationSeverity.BLOCKING,
                "explicitly pinned broker identity",
                observed,
                "Observed identity is captured, but no trusted expected value was configured.",
            )
            return
        self._equality(
            checks,
            code=code,
            field=field,
            expected=expected,
            observed=observed,
            mismatch=ValidationSeverity.BLOCKING,
            mismatch_message="Broker identity differs from the explicitly configured expectation.",
        )

    @staticmethod
    def _add(  # noqa: PLR0917 - explicit check fields are audit data
        checks: list[BrokerValidationCheck],
        code: str,
        field: str,
        severity: ValidationSeverity,
        expected: Any,
        observed: Any,
        message: str,
    ) -> None:
        checks.append(
            BrokerValidationCheck(
                code=code,
                field=field,
                severity=severity,
                expected=expected,
                observed=observed,
                message=message,
            )
        )
