"""Deterministic, event-driven, paper-only historical simulation."""

from fx_platform.backtesting.clock import BacktestClock
from fx_platform.backtesting.dataset import (
    CSV_COLUMNS,
    HistoricalBar,
    HistoricalDataset,
    HistoricalDatasetMetadata,
    HistoricalEventStream,
)
from fx_platform.backtesting.engine import BacktestConfigurationError, BacktestEngine
from fx_platform.backtesting.models import (
    AuditEventType,
    BacktestAuditEvent,
    BacktestReport,
    BacktestResult,
    BacktestRunMetadata,
    ExecutionConfiguration,
    ExitReason,
    SimulatedPosition,
    StrategyConfiguration,
    TradeRecord,
)
from fx_platform.backtesting.splits import DatasetSplit, split_chronologically

__all__ = [
    "CSV_COLUMNS",
    "AuditEventType",
    "BacktestAuditEvent",
    "BacktestClock",
    "BacktestConfigurationError",
    "BacktestEngine",
    "BacktestReport",
    "BacktestResult",
    "BacktestRunMetadata",
    "DatasetSplit",
    "ExecutionConfiguration",
    "ExitReason",
    "HistoricalBar",
    "HistoricalDataset",
    "HistoricalDatasetMetadata",
    "HistoricalEventStream",
    "SimulatedPosition",
    "StrategyConfiguration",
    "TradeRecord",
    "split_chronologically",
]
