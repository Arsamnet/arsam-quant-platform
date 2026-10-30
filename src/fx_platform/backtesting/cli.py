"""Local deterministic backtest command with no network or database dependency."""

import argparse
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from fx_platform.adapters.market import bootstrap_symbol_specifications
from fx_platform.backtesting.broker import BacktestExecutionError
from fx_platform.backtesting.dataset import HistoricalDataset
from fx_platform.backtesting.engine import BacktestConfigurationError, BacktestEngine
from fx_platform.backtesting.models import ExecutionConfiguration, StrategyConfiguration
from fx_platform.domain.risk import RiskLimits
from fx_platform.domain.strategy import PreviousCloseMomentumStrategy


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fx-backtest",
        description="Run the deterministic paper-only historical simulator.",
    )
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--initial-balance", required=True, type=Decimal)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dataset-id")
    parser.add_argument("--dataset-version", default="1")
    parser.add_argument("--source", default="local_csv")
    parser.add_argument("--account-currency", default="USD")
    parser.add_argument("--commission-per-lot-per-side", type=Decimal, default=Decimal("3.50"))
    parser.add_argument("--slippage-ticks", type=Decimal, default=Decimal(1))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Validate inputs, execute one deterministic run, and optionally write canonical JSON."""
    arguments = _parser().parse_args(argv)
    dataset_path: Path = arguments.dataset
    try:
        dataset = HistoricalDataset.from_csv(
            dataset_path,
            dataset_id=arguments.dataset_id or dataset_path.stem,
            dataset_version=arguments.dataset_version,
            source=arguments.source,
        )
        symbols = frozenset(dataset.metadata.symbols)
        strategy = PreviousCloseMomentumStrategy()
        strategy_configuration = StrategyConfiguration.create(
            strategy_id=strategy.name,
            strategy_version=strategy.version,
            parameters={
                "volume": strategy.volume,
                "stop_distance_ticks": strategy.stop_distance_ticks,
                "reward_to_risk": strategy.reward_to_risk,
            },
        )
        result = BacktestEngine(
            strategy=strategy,
            strategy_configuration=strategy_configuration,
            risk_limits=RiskLimits(allowed_symbols=symbols),
            symbol_specifications=bootstrap_symbol_specifications(symbols),
            execution_configuration=ExecutionConfiguration(
                commission_per_lot_per_side=arguments.commission_per_lot_per_side,
                slippage_ticks=arguments.slippage_ticks,
            ),
            account_currency=arguments.account_currency,
        ).run(dataset, starting_balance=arguments.initial_balance)
        if arguments.output is not None:
            _write_result(arguments.output, result.to_json())
        sys.stdout.write(
            "Backtest complete "
            f"run_id={result.metadata.run_id} "
            f"trades={result.report.trade_count} "
            f"final_balance={result.report.final_balance} "
            f"net_pnl={result.report.net_pnl}\n"
        )
    except (BacktestConfigurationError, BacktestExecutionError, OSError, ValueError) as error:
        sys.stderr.write(f"Backtest failed: {error}\n")
        return 2
    return 0


def _write_result(output_path: Path, payload: str) -> None:
    if not output_path.parent.is_dir():
        raise ValueError(f"output parent directory does not exist: {output_path.parent}")
    output_path.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
