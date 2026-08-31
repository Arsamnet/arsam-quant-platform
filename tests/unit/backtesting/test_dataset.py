"""Historical schema, validation, identity, and chronological splitting tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from fx_platform.backtesting import (
    HistoricalBar,
    HistoricalDataset,
    HistoricalDatasetMetadata,
    HistoricalEventStream,
)
from fx_platform.backtesting.dataset import timeframe_duration
from fx_platform.backtesting.splits import split_chronologically
from tests.backtesting_helpers import sample_dataset

NOW = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)


def _bar(*, minute: int = 0, **changes: object) -> HistoricalBar:
    values: dict[str, object] = {
        "symbol": "EURUSD",
        "timeframe": "M1",
        "opened_at": NOW + timedelta(minutes=minute),
        "bid_open": Decimal("1.1000"),
        "bid_high": Decimal("1.1010"),
        "bid_low": Decimal("1.0990"),
        "bid_close": Decimal("1.1005"),
        "spread": Decimal("0.0002"),
    }
    values.update(changes)
    return HistoricalBar(**values)


def test_csv_fixture_has_explicit_spread_and_stable_content_identity() -> None:
    first = sample_dataset()
    second = HistoricalDataset.create(
        dataset_id="synthetic-eurusd-m1",
        dataset_version="1.0.0",
        source="committed_synthetic_fixture",
        bars=tuple(replace(bar, bid_open=Decimal(f"{bar.bid_open}0")) for bar in first.bars),
    )

    assert first.metadata.checksum == second.metadata.checksum
    assert first.metadata.event_count == 6
    assert first.metadata.symbols == ("EURUSD",)
    assert first.metadata.timezone == "UTC"
    assert first.bars[0].ask_open == Decimal("1.1002")
    assert first.bars[0].ask_high == Decimal("1.1004")
    assert first.bars[0].ask_low == Decimal("1.1000")
    assert first.bars[0].ask_close == Decimal("1.1002")
    assert first.bars[0].midpoint_open == Decimal("1.1001")
    assert first.bars[0].midpoint_close == Decimal("1.1001")
    assert tuple(HistoricalEventStream(first)) == first.bars


@pytest.mark.parametrize(
    "changes",
    [
        {"opened_at": NOW.replace(tzinfo=None)},
        {"symbol": "eurusd"},
        {"timeframe": "TICK"},
        {"bid_open": Decimal(0)},
        {"bid_high": Decimal("1.0999")},
        {"bid_low": Decimal("1.1006")},
        {"spread": Decimal(-1)},
        {"spread": Decimal("Infinity")},
    ],
)
def test_historical_bar_rejects_malformed_financial_state(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _bar(**changes)


def test_dataset_rejects_duplicates_reverse_order_and_mixed_timeframes() -> None:
    with pytest.raises(ValueError, match="at least one"):
        HistoricalDataset.create(
            dataset_id="fixture",
            dataset_version="1",
            source="synthetic",
            bars=(),
        )
    with pytest.raises(ValueError, match="duplicate"):
        HistoricalDataset.create(
            dataset_id="fixture",
            dataset_version="1",
            source="synthetic",
            bars=(_bar(), _bar()),
        )
    with pytest.raises(ValueError, match="chronological"):
        HistoricalDataset.create(
            dataset_id="fixture",
            dataset_version="1",
            source="synthetic",
            bars=(_bar(minute=1), _bar()),
        )
    with pytest.raises(ValueError, match="one timeframe"):
        HistoricalDataset.create(
            dataset_id="fixture",
            dataset_version="1",
            source="synthetic",
            bars=(_bar(), _bar(minute=1, timeframe="M5")),
        )


def test_csv_loader_rejects_bad_header_naive_timestamp_and_missing_file(tmp_path: Path) -> None:
    bad_header = tmp_path / "bad-header.csv"
    bad_header.write_text("timestamp,symbol\n2026-01-01T00:00:00Z,EURUSD\n", encoding="utf-8")
    naive = tmp_path / "naive.csv"
    naive.write_text(
        "timestamp,symbol,timeframe,bid_open,bid_high,bid_low,bid_close,spread\n"
        "2026-01-01T00:00:00,EURUSD,M1,1.1,1.2,1.0,1.1,0.0002\n",
        encoding="utf-8",
    )

    for path in (bad_header, naive, tmp_path / "missing.csv"):
        with pytest.raises(ValueError):
            HistoricalDataset.from_csv(
                path,
                dataset_id="fixture",
                dataset_version="1",
                source="synthetic",
            )

    empty_value = tmp_path / "empty.csv"
    empty_value.write_text(
        "timestamp,symbol,timeframe,bid_open,bid_high,bid_low,bid_close,spread\n"
        "2026-01-01T00:00:00Z,EURUSD,M1,1.1,1.2,1.0,1.1,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="empty"):
        HistoricalDataset.from_csv(
            empty_value,
            dataset_id="fixture",
            dataset_version="1",
            source="synthetic",
        )

    extra_value = tmp_path / "extra.csv"
    extra_value.write_text(
        "timestamp,symbol,timeframe,bid_open,bid_high,bid_low,bid_close,spread\n"
        "2026-01-01T00:00:00Z,EURUSD,M1,1.1,1.2,1.0,1.1,0.0002,unexpected\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="schema"):
        HistoricalDataset.from_csv(
            extra_value,
            dataset_id="fixture",
            dataset_version="1",
            source="synthetic",
        )


def test_csv_loader_explicitly_normalizes_aware_offsets_to_utc(tmp_path: Path) -> None:
    path = tmp_path / "offset.csv"
    path.write_text(
        "timestamp,symbol,timeframe,bid_open,bid_high,bid_low,bid_close,spread\n"
        "2026-01-01T03:30:00+03:30,EURUSD,M1,1.1,1.2,1.0,1.1,0.0002\n",
        encoding="utf-8",
    )

    dataset = HistoricalDataset.from_csv(
        path,
        dataset_id="fixture",
        dataset_version="1",
        source="synthetic",
    )

    assert dataset.bars[0].opened_at == datetime(2026, 1, 1, tzinfo=UTC)


def test_chronological_split_preserves_order_without_overlap_or_leakage() -> None:
    dataset = sample_dataset()
    split = split_chronologically(
        dataset,
        in_sample_fraction=Decimal("0.5"),
        validation_fraction=Decimal("0.25"),
    )

    assert split.in_sample.bars == dataset.bars[:3]
    assert split.validation.bars == dataset.bars[3:4]
    assert split.out_of_sample.bars == dataset.bars[4:]
    assert split.in_sample.metadata.end_at <= split.validation.metadata.start_at
    assert split.validation.metadata.end_at <= split.out_of_sample.metadata.start_at
    assert set(split.in_sample.bars).isdisjoint(split.validation.bars)


@pytest.mark.parametrize(
    ("in_sample", "validation"),
    [
        (Decimal(0), Decimal("0.2")),
        (Decimal("0.8"), Decimal("0.2")),
        (Decimal("0.1"), Decimal("0.1")),
    ],
)
def test_split_rejects_invalid_or_empty_partitions(
    in_sample: Decimal,
    validation: Decimal,
) -> None:
    with pytest.raises(ValueError):
        split_chronologically(
            sample_dataset(),
            in_sample_fraction=in_sample,
            validation_fraction=validation,
        )


def test_supported_timeframes_are_explicit() -> None:
    assert timeframe_duration("H1") == timedelta(hours=1)
    with pytest.raises(ValueError, match="unsupported"):
        timeframe_duration("H4")


@pytest.mark.parametrize(
    "changes",
    [
        {"dataset_id": ""},
        {"schema_version": "2.0"},
        {"symbols": ()},
        {"symbols": ("USDJPY", "EURUSD")},
        {"end_at": NOW},
        {"event_count": 0},
        {"timezone": "Asia/Tehran"},
        {"checksum": "not-a-checksum"},
    ],
)
def test_dataset_metadata_rejects_invalid_identity(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "dataset_id": "fixture",
        "schema_version": "1.0",
        "dataset_version": "1",
        "source": "synthetic",
        "symbols": ("EURUSD",),
        "timeframe": "M1",
        "start_at": NOW,
        "end_at": NOW + timedelta(minutes=1),
        "event_count": 1,
        "timezone": "UTC",
        "checksum": "a" * 64,
    }
    values.update(changes)
    with pytest.raises(ValueError):
        HistoricalDatasetMetadata(**values)


def test_dataset_rejects_metadata_that_does_not_match_content() -> None:
    dataset = sample_dataset()
    mismatched = replace(dataset.metadata, checksum="0" * 64)

    with pytest.raises(ValueError, match="does not match"):
        HistoricalDataset(metadata=mismatched, bars=dataset.bars)
