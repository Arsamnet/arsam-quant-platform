"""Offline import, validation, and diff commands for read-only broker evidence."""

import argparse
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fx_platform.adapters.market import bootstrap_symbol_specifications
from fx_platform.broker_validation.diff import BrokerContractDiff
from fx_platform.broker_validation.models import (
    AccountPositionMode,
    ValidationOverallStatus,
)
from fx_platform.broker_validation.parser import BrokerSnapshotParseError, load_broker_snapshot
from fx_platform.broker_validation.validation import BrokerContractValidator, ValidationPolicy
from fx_platform.domain.market import SymbolSpecification

logger = logging.getLogger(__name__)


def import_main(argv: Sequence[str] | None = None) -> int:
    """Parse, fingerprint, summarize, and optionally archive canonical snapshot JSON."""
    parser = argparse.ArgumentParser(
        prog="fx-mt5-import",
        description="Import a read-only MT5 metadata snapshot without broker connectivity.",
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expect-fingerprint")
    arguments = parser.parse_args(argv)
    try:
        snapshot = load_broker_snapshot(
            arguments.input,
            expected_fingerprint=arguments.expect_fingerprint,
        )
        if arguments.output is not None:
            _write(arguments.output, snapshot.to_json())
        logger.info(
            "broker snapshot imported",
            extra={
                "snapshot_fingerprint": snapshot.snapshot_fingerprint,
                "contract_fingerprint": snapshot.contract_fingerprint,
            },
        )
        sys.stdout.write(
            "Snapshot imported "
            f"schema={snapshot.schema_version} "
            f"symbols={','.join(symbol.name for symbol in snapshot.symbols) or 'none'} "
            f"snapshot_fingerprint={snapshot.snapshot_fingerprint} "
            f"contract_fingerprint={snapshot.contract_fingerprint}\n"
        )
    except (BrokerSnapshotParseError, OSError, ValueError) as error:
        sys.stderr.write(f"MT5 import failed: {error}\n")
        return 2
    return 0


def validate_main(argv: Sequence[str] | None = None) -> int:
    """Compare a snapshot to reviewed platform metadata and emit a canonical report."""
    parser = argparse.ArgumentParser(
        prog="fx-broker-validate",
        description="Validate read-only broker metadata against platform assumptions.",
    )
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--as-of", required=True, help="Explicit aware timestamp for freshness")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expect-fingerprint")
    parser.add_argument("--account-currency", default="USD")
    parser.add_argument("--expected-broker-company")
    parser.add_argument("--expected-broker-server")
    parser.add_argument(
        "--expected-account-mode",
        choices=("retail_hedging", "retail_netting", "exchange"),
        default="retail_hedging",
    )
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument("--absolute-money-tolerance", default="0.01")
    parser.add_argument("--relative-money-tolerance", default="0.0001")
    parser.add_argument("--price-tolerance-ticks", default="0")
    arguments = parser.parse_args(argv)
    symbol = arguments.symbol.upper()
    try:
        snapshot = load_broker_snapshot(
            arguments.snapshot,
            expected_fingerprint=arguments.expect_fingerprint,
        )
        specification = _expected_specification(symbol)
        maximum_age = _nonnegative_seconds(arguments.max_snapshot_age_seconds)
        policy = ValidationPolicy(
            expected_account_currency=arguments.account_currency.upper(),
            expected_position_mode=AccountPositionMode(arguments.expected_account_mode),
            expected_broker_company=arguments.expected_broker_company,
            expected_broker_server=arguments.expected_broker_server,
            maximum_snapshot_age=maximum_age,
            absolute_money_tolerance=_decimal_argument(
                arguments.absolute_money_tolerance, "absolute money tolerance"
            ),
            relative_money_tolerance=_decimal_argument(
                arguments.relative_money_tolerance, "relative money tolerance"
            ),
            price_tolerance_ticks=_decimal_argument(
                arguments.price_tolerance_ticks, "price tolerance ticks"
            ),
        )
        report = BrokerContractValidator().validate(
            expected=specification,
            snapshot=snapshot,
            symbol=symbol,
            policy=policy,
            as_of=_aware_timestamp(arguments.as_of),
        )
        if arguments.output is not None:
            _write(arguments.output, report.to_json())
        logger.log(
            logging.ERROR
            if report.overall_status is ValidationOverallStatus.BLOCKING_MISMATCH
            else logging.INFO,
            "broker snapshot validated",
            extra={
                "snapshot_fingerprint": report.snapshot_fingerprint,
                "contract_fingerprint": report.contract_fingerprint,
                "validation_symbol": report.symbol,
                "validation_status": report.overall_status.value,
            },
        )
        blocking_count = sum(check.severity.value == "blocking" for check in report.checks)
        warning_count = sum(check.severity.value == "warning" for check in report.checks)
        sys.stdout.write(
            "Broker validation complete "
            f"symbol={symbol} status={report.overall_status.value} "
            f"readiness={report.readiness.value} blocking={blocking_count} "
            f"warnings={warning_count}\n"
        )
        return (  # noqa: TRY300 - CLI exit belongs beside its emitted report
            3 if report.overall_status is ValidationOverallStatus.BLOCKING_MISMATCH else 0
        )
    except (BrokerSnapshotParseError, InvalidOperation, OSError, ValueError) as error:
        sys.stderr.write(f"Broker validation failed: {error}\n")
        return 2


def diff_main(argv: Sequence[str] | None = None) -> int:
    """Compare two snapshots with contract/dynamic classifications."""
    parser = argparse.ArgumentParser(
        prog="fx-broker-diff",
        description="Compare two canonical read-only broker snapshots.",
    )
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)
    try:
        result = BrokerContractDiff.between(
            load_broker_snapshot(arguments.before),
            load_broker_snapshot(arguments.after),
        )
        if arguments.output is not None:
            _write(arguments.output, result.to_json())
        sys.stdout.write(
            "Broker diff complete "
            f"contract_changed={str(result.contract_changed).lower()} "
            f"contract_changes={len(result.contract_changes)} "
            f"dynamic_changes={len(result.dynamic_changes)}\n"
        )
    except (BrokerSnapshotParseError, OSError, ValueError) as error:
        sys.stderr.write(f"Broker diff failed: {error}\n")
        return 2
    return 0


def _write(path: Path, payload: str) -> None:
    if not path.parent.is_dir():
        raise ValueError(f"output parent directory does not exist: {path.parent}")
    path.write_text(payload + "\n", encoding="utf-8")


def _aware_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("--as-of must be a valid ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--as-of must include a UTC offset")
    return parsed.astimezone(UTC)


def _decimal_argument(value: str, field: str) -> Decimal:
    result = Decimal(value)
    if not result.is_finite() or result < Decimal(0):
        raise ValueError(f"{field} must be a non-negative finite decimal")
    return result


def _expected_specification(symbol: str) -> SymbolSpecification:
    specification = bootstrap_symbol_specifications(frozenset({symbol})).get(symbol)
    if specification is None:
        raise ValueError("expected platform symbol specification is unavailable")
    return specification


def _nonnegative_seconds(value: int) -> timedelta:
    if value < 0:
        raise ValueError("maximum snapshot age must not be negative")
    return timedelta(seconds=value)
