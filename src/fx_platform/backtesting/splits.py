"""Leakage-resistant chronological research dataset partitions."""

from dataclasses import dataclass
from decimal import Decimal

from fx_platform.backtesting.dataset import HistoricalBar, HistoricalDataset
from fx_platform.domain.common import require_finite_decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class DatasetSplit:
    """Non-overlapping chronological in-sample, validation, and out-of-sample data."""

    in_sample: HistoricalDataset
    validation: HistoricalDataset
    out_of_sample: HistoricalDataset


def split_chronologically(
    dataset: HistoricalDataset,
    *,
    in_sample_fraction: Decimal,
    validation_fraction: Decimal,
) -> DatasetSplit:
    """Split by row order without shuffling, overlap, or future leakage."""
    for field_name, value in (
        ("in_sample_fraction", in_sample_fraction),
        ("validation_fraction", validation_fraction),
    ):
        require_finite_decimal(value, field_name)
        if value <= Decimal(0) or value >= Decimal(1):
            raise ValueError(f"{field_name} must be between zero and one")
    if in_sample_fraction + validation_fraction >= Decimal(1):
        raise ValueError("split fractions must leave an out-of-sample partition")

    event_count = len(dataset.bars)
    in_sample_end = int(Decimal(event_count) * in_sample_fraction)
    validation_end = in_sample_end + int(Decimal(event_count) * validation_fraction)
    if in_sample_end < 1 or validation_end <= in_sample_end or validation_end >= event_count:
        raise ValueError("dataset is too small for three non-empty chronological partitions")

    return DatasetSplit(
        in_sample=_partition(dataset, "in_sample", dataset.bars[:in_sample_end]),
        validation=_partition(
            dataset,
            "validation",
            dataset.bars[in_sample_end:validation_end],
        ),
        out_of_sample=_partition(
            dataset,
            "out_of_sample",
            dataset.bars[validation_end:],
        ),
    )


def _partition(
    dataset: HistoricalDataset,
    name: str,
    bars: tuple[HistoricalBar, ...],
) -> HistoricalDataset:
    return HistoricalDataset.create(
        dataset_id=f"{dataset.metadata.dataset_id}:{name}",
        dataset_version=dataset.metadata.dataset_version,
        source=dataset.metadata.source,
        bars=bars,
    )
