"""Deterministic builders shared by backtesting suites."""

from decimal import Decimal
from pathlib import Path

from fx_platform.adapters.market import bootstrap_symbol_specifications
from fx_platform.backtesting import (
    BacktestEngine,
    ExecutionConfiguration,
    HistoricalDataset,
    StrategyConfiguration,
)
from fx_platform.domain.risk import RiskLimits
from fx_platform.domain.strategy import PreviousCloseMomentumStrategy

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "backtesting" / "eurusd_sample.csv"


def sample_dataset() -> HistoricalDataset:
    return HistoricalDataset.from_csv(
        FIXTURE_PATH,
        dataset_id="synthetic-eurusd-m1",
        dataset_version="1.0.0",
        source="committed_synthetic_fixture",
    )


def make_backtest_engine(
    *,
    commission: Decimal = Decimal("3.50"),
    slippage_ticks: Decimal = Decimal(1),
    risk_limits: RiskLimits | None = None,
) -> BacktestEngine:
    strategy = PreviousCloseMomentumStrategy()
    limits = risk_limits or RiskLimits(allowed_symbols=frozenset({"EURUSD"}))
    return BacktestEngine(
        strategy=strategy,
        strategy_configuration=StrategyConfiguration.create(
            strategy_id=strategy.name,
            strategy_version=strategy.version,
            parameters={
                "volume": strategy.volume,
                "stop_distance": strategy.stop_distance,
                "reward_to_risk": strategy.reward_to_risk,
            },
        ),
        risk_limits=limits,
        symbol_specifications=bootstrap_symbol_specifications(limits.allowed_symbols),
        execution_configuration=ExecutionConfiguration(
            commission_per_lot_per_side=commission,
            slippage_ticks=slippage_ticks,
        ),
    )
