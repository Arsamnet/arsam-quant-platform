"""Local CLI success and fail-closed input behavior."""

import json
from pathlib import Path

from fx_platform.backtesting.cli import main
from tests.backtesting_helpers import FIXTURE_PATH


def test_cli_runs_fixture_and_writes_canonical_json(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "report.json"

    exit_code = main(
        [
            "--dataset",
            str(FIXTURE_PATH),
            "--initial-balance",
            "10000",
            "--output",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "trades=1" in captured.out
    assert json.loads(output.read_text(encoding="utf-8"))["report"]["net_pnl"] == "-1.09"


def test_cli_returns_nonzero_for_invalid_input(tmp_path: Path, capsys) -> None:
    exit_code = main(
        [
            "--dataset",
            str(tmp_path / "missing.csv"),
            "--initial-balance",
            "10000",
        ]
    )

    assert exit_code == 2
    assert "Backtest failed" in capsys.readouterr().err
