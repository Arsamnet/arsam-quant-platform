"""Static regression checks for the controlled USDJPY DEMO submission harness."""

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[2]
HARNESS = REPOSITORY_ROOT / "scripts" / "invoke-reviewed-usdjpy-demo-decision.ps1"


def test_harness_fails_closed_before_or_during_single_submission() -> None:
    source = HARNESS.read_text(encoding="utf-8")

    assert '$ErrorActionPreference = "Stop"' in source
    assert "Set-StrictMode -Version Latest" in source
    assert 'Write-Error ("BLOCKED before submission: " + $_.Exception.Message)' in source
    assert "Submission outcome may be ambiguous" in source
    assert "DO NOT rerun" in source
    assert "exit 1" in source

    assert source.count("Assert-FreshObservation -Symbol $UsdJpy") == 2
    assert source.count('-Uri "http://127.0.0.1:8000/v1/decision"') == 1
    assert "Durable execution state is unresolved" in source


def test_harness_locks_reviewed_environment_and_inverse_quote_provenance() -> None:
    source = HARNESS.read_text(encoding="utf-8")

    assert '"FIBO Group, Ltd"' in source
    assert '"FIBOGroup-MT5 Server"' in source
    assert "$Meta.account.trade_mode_code -ne 0" in source
    assert "$Meta.account.margin_mode_code -ne 2" in source
    assert "$Meta.account.leverage -ne 100" in source
    assert 'source_currency = "JPY"' in source
    assert 'target_currency = "USD"' in source
    assert 'source_symbol = "USDJPY"' in source
    assert 'pair_base_currency = "USD"' in source
    assert 'pair_quote_currency = "JPY"' in source
