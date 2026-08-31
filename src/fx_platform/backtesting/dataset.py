"""Strict immutable historical bar datasets with content-derived identity."""

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fx_platform.backtesting.serialization import fingerprint
from fx_platform.domain.common import require_finite_decimal, require_utc

DATASET_SCHEMA_VERSION = "1.0"
CSV_COLUMNS = (
    "timestamp",
    "symbol",
    "timeframe",
    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "spread",
)
_TIMEFRAME_DURATIONS = {
    "M1": timedelta(minutes=1),
    "M5": timedelta(minutes=5),
    "M15": timedelta(minutes=15),
    "H1": timedelta(hours=1),
    "D1": timedelta(days=1),
}
_SHA256_HEX_LENGTH = 64


def timeframe_duration(timeframe: str) -> timedelta:
    """Return an explicitly supported fixed bar duration."""
    try:
        return _TIMEFRAME_DURATIONS[timeframe]
    except KeyError as error:
        raise ValueError(f"unsupported timeframe: {timeframe}") from error


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoricalBar:
    """One fully closed Bid OHLC bar with a fixed explicit Bid/Ask spread."""

    symbol: str
    timeframe: str
    opened_at: datetime
    bid_open: Decimal
    bid_high: Decimal
    bid_low: Decimal
    bid_close: Decimal
    spread: Decimal

    def __post_init__(self) -> None:
        require_utc(self.opened_at, "opened_at")
        if not self.symbol or self.symbol != self.symbol.upper():
            raise ValueError("symbol must be non-empty uppercase text")
        timeframe_duration(self.timeframe)
        for field_name, value in (
            ("bid_open", self.bid_open),
            ("bid_high", self.bid_high),
            ("bid_low", self.bid_low),
            ("bid_close", self.bid_close),
            ("spread", self.spread),
        ):
            require_finite_decimal(value, field_name)
        if min(self.bid_open, self.bid_high, self.bid_low, self.bid_close) <= Decimal(0):
            raise ValueError("Bid OHLC values must be greater than zero")
        if self.spread < Decimal(0):
            raise ValueError("spread must not be negative")
        if self.bid_low > min(self.bid_open, self.bid_close):
            raise ValueError("bid_low must not exceed bid_open or bid_close")
        if self.bid_high < max(self.bid_open, self.bid_close):
            raise ValueError("bid_high must not be below bid_open or bid_close")

    @property
    def closed_at(self) -> datetime:
        """Return the logical close instant at which the complete bar becomes visible."""
        return self.opened_at + timeframe_duration(self.timeframe)

    @property
    def ask_open(self) -> Decimal:
        return self.bid_open + self.spread

    @property
    def ask_high(self) -> Decimal:
        return self.bid_high + self.spread

    @property
    def ask_low(self) -> Decimal:
        return self.bid_low + self.spread

    @property
    def ask_close(self) -> Decimal:
        return self.bid_close + self.spread

    @property
    def midpoint_open(self) -> Decimal:
        return self.bid_open + (self.spread / Decimal(2))

    @property
    def midpoint_close(self) -> Decimal:
        return self.bid_close + (self.spread / Decimal(2))

    def canonical_content(self) -> dict[str, object]:
        """Return filesystem-independent logical bar content."""
        return {
            "timestamp": self.opened_at,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "bid_open": self.bid_open,
            "bid_high": self.bid_high,
            "bid_low": self.bid_low,
            "bid_close": self.bid_close,
            "spread": self.spread,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoricalDatasetMetadata:
    """Immutable logical identity and coverage of one historical dataset."""

    dataset_id: str
    schema_version: str
    dataset_version: str
    source: str
    symbols: tuple[str, ...]
    timeframe: str
    start_at: datetime
    end_at: datetime
    event_count: int
    timezone: str
    checksum: str

    def __post_init__(self) -> None:
        require_utc(self.start_at, "start_at")
        require_utc(self.end_at, "end_at")
        if not self.dataset_id or not self.dataset_version or not self.source:
            raise ValueError("dataset identity fields must not be empty")
        if self.schema_version != DATASET_SCHEMA_VERSION:
            raise ValueError("unsupported dataset schema version")
        if not self.symbols or tuple(sorted(set(self.symbols))) != self.symbols:
            raise ValueError("dataset symbols must be unique and sorted")
        timeframe_duration(self.timeframe)
        if self.end_at <= self.start_at:
            raise ValueError("dataset end_at must be after start_at")
        if self.event_count < 1:
            raise ValueError("dataset event_count must be positive")
        if self.timezone != "UTC":
            raise ValueError("dataset timezone must be UTC")
        if len(self.checksum) != _SHA256_HEX_LENGTH or any(
            character not in "0123456789abcdef" for character in self.checksum
        ):
            raise ValueError("dataset checksum must be lowercase SHA-256")

    def canonical_identity(self) -> dict[str, object]:
        """Return the reproducibility identity embedded in every run."""
        return {
            "dataset_id": self.dataset_id,
            "schema_version": self.schema_version,
            "dataset_version": self.dataset_version,
            "source": self.source,
            "symbols": self.symbols,
            "timeframe": self.timeframe,
            "start_at": self.start_at,
            "end_at": self.end_at,
            "event_count": self.event_count,
            "timezone": self.timezone,
            "checksum": self.checksum,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoricalDataset:
    """Validated bars preserved in the exact supplied chronological order."""

    metadata: HistoricalDatasetMetadata
    bars: tuple[HistoricalBar, ...]

    def __post_init__(self) -> None:
        _validate_bars(self.bars)
        expected = _metadata(
            dataset_id=self.metadata.dataset_id,
            dataset_version=self.metadata.dataset_version,
            source=self.metadata.source,
            bars=self.bars,
        )
        if self.metadata != expected:
            raise ValueError("dataset metadata does not match canonical content")

    @classmethod
    def create(
        cls,
        *,
        dataset_id: str,
        dataset_version: str,
        source: str,
        bars: tuple[HistoricalBar, ...],
    ) -> "HistoricalDataset":
        """Validate bars and derive immutable metadata without a filesystem identity."""
        _validate_bars(bars)
        return cls(
            metadata=_metadata(
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                source=source,
                bars=bars,
            ),
            bars=bars,
        )

    @classmethod
    def from_csv(
        cls,
        path: Path,
        *,
        dataset_id: str,
        dataset_version: str,
        source: str,
    ) -> "HistoricalDataset":
        """Load a strict UTF-8 CSV; no row is silently reordered or repaired."""
        if not path.is_file():
            raise ValueError(f"historical dataset is not a file: {path}")
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
                raise ValueError("historical CSV header does not match schema 1.0")
            bars = tuple(
                _bar_from_row(row, line_number) for line_number, row in enumerate(reader, 2)
            )
        return cls.create(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            source=source,
            bars=bars,
        )


@dataclass(frozen=True, slots=True)
class HistoricalEventStream:
    """Expose only forward chronological iteration, never a future-aware frame."""

    _dataset: HistoricalDataset

    def __iter__(self) -> Iterator[HistoricalBar]:
        return iter(self._dataset.bars)


def _validate_bars(bars: tuple[HistoricalBar, ...]) -> None:
    if not bars:
        raise ValueError("historical dataset must contain at least one bar")
    identities: set[tuple[str, str, datetime]] = set()
    previous_time: datetime | None = None
    timeframes: set[str] = set()
    for bar in bars:
        identity = (bar.symbol, bar.timeframe, bar.opened_at)
        if identity in identities:
            raise ValueError("duplicate historical bar identity")
        if previous_time is not None and bar.opened_at < previous_time:
            raise ValueError("historical bars must already be chronological")
        identities.add(identity)
        timeframes.add(bar.timeframe)
        previous_time = bar.opened_at
    if len(timeframes) != 1:
        raise ValueError("one dataset must use exactly one timeframe")


def _metadata(
    *,
    dataset_id: str,
    dataset_version: str,
    source: str,
    bars: tuple[HistoricalBar, ...],
) -> HistoricalDatasetMetadata:
    _validate_bars(bars)
    checksum = fingerprint(
        {
            "schema_version": DATASET_SCHEMA_VERSION,
            "bars": tuple(bar.canonical_content() for bar in bars),
        }
    )
    return HistoricalDatasetMetadata(
        dataset_id=dataset_id,
        schema_version=DATASET_SCHEMA_VERSION,
        dataset_version=dataset_version,
        source=source,
        symbols=tuple(sorted({bar.symbol for bar in bars})),
        timeframe=bars[0].timeframe,
        start_at=bars[0].opened_at,
        end_at=max(bar.closed_at for bar in bars),
        event_count=len(bars),
        timezone="UTC",
        checksum=checksum,
    )


def _bar_from_row(row: dict[str, str | None], line_number: int) -> HistoricalBar:
    if tuple(row) != CSV_COLUMNS:
        raise ValueError(f"historical CSV row {line_number} does not match schema 1.0")
    if any(value is None or value == "" for value in row.values()):
        raise ValueError(f"historical CSV row {line_number} contains an empty value")
    try:
        timestamp_text = str(row["timestamp"])
        parsed = _parse_timestamp(timestamp_text)
        opened_at = parsed.astimezone(UTC)
        return HistoricalBar(
            symbol=str(row["symbol"]),
            timeframe=str(row["timeframe"]),
            opened_at=opened_at,
            bid_open=Decimal(str(row["bid_open"])),
            bid_high=Decimal(str(row["bid_high"])),
            bid_low=Decimal(str(row["bid_low"])),
            bid_close=Decimal(str(row["bid_close"])),
            spread=Decimal(str(row["spread"])),
        )
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"invalid historical CSV row {line_number}: {error}") from error


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed
