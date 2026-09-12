"""Defense-in-depth read-only MQL5 lexical safety checks."""

from pathlib import Path

import pytest

from fx_platform.broker_validation.safety import (
    forbidden_trade_api_matches,
    scan_read_only_probe,
    validate_mql5_execution_boundary,
)

REPOSITORY_ROOT = Path(__file__).parents[3]
PROBE_PATH = REPOSITORY_ROOT / "mt5" / "metadata_probe" / "ReadOnlyMetadataProbe.mq5"
MT5_ROOT = REPOSITORY_ROOT / "mt5"
GUARD_PATH = MT5_ROOT / "execution_guard" / "ArsamDemoExecutionGuard.mq5"


def test_repository_read_only_probe_contains_no_forbidden_trade_api() -> None:
    assert scan_read_only_probe(PROBE_PATH) == ()


def test_repository_has_exactly_one_reviewed_mql5_execution_boundary() -> None:
    assert validate_mql5_execution_boundary(REPOSITORY_ROOT, GUARD_PATH) == ()


@pytest.mark.parametrize(
    "guard_fragment",
    [
        "ACCOUNT_TRADE_MODE_DEMO",
        "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING",
        "ValidLoopbackBaseUrl(LocalApiBaseUrl)",
        "StringLen(ExecutionToken)<32",
        "MaximumFutureSkewSeconds!=REVIEWED_FUTURE_SKEW_SECONDS",
        "MaximumDeviationPoints!=REVIEWED_DEVIATION_POINTS",
        'int fractional=StringFind(value,".")',
        "work.volume>HARD_MAX_VOLUME",
        "work.stop_loss<=0.0 || work.take_profit<=0.0",
        "OrderCheck(request,check)",
        'AppendJournal(work,"submitted",marker)',
        'AppendJournal(work,"unknown",marker)',
        "BrokerMarkerExists(marker",
    ],
)
def test_repository_execution_guard_retains_reviewed_fail_closed_controls(
    guard_fragment: str,
) -> None:
    assert guard_fragment in GUARD_PATH.read_text(encoding="utf-8")


def test_execution_boundary_scan_rejects_order_send_outside_guard(tmp_path: Path) -> None:
    root = tmp_path / "mt5"
    root.mkdir()
    guard = root / "guard.mq5"
    guard.write_text("void f(){ OrderSend(request,result); }", encoding="utf-8")
    (root / "unreviewed.mq5").write_text("void g(){ OrderSend(request,result); }", encoding="utf-8")

    violations = validate_mql5_execution_boundary(root, guard)

    assert any("unreviewed.mq5" in violation for violation in violations)


@pytest.mark.parametrize(
    "source",
    [
        "void f(){ OrderSend(request, result); }",
        "void f(){ OrderSendAsync(request, result); }",
        "CTrade trade;",
        "void f(){ Buy(1); }",
        "void f(){ Sell(1); }",
        "void f(){ PositionOpen(); }",
        "void f(){ PositionClose(); }",
        "void f(){ OrderDelete(); }",
        "void f(){ OrderModify(); }",
    ],
)
def test_safety_scan_detects_executable_forbidden_apis(source: str) -> None:
    assert forbidden_trade_api_matches(source)


def test_safety_scan_ignores_comments_strings_and_allows_read_only_calculations() -> None:
    source = """
    // OrderSend(request, result);
    /* CTrade trade; PositionClose(); */
    string explanation = "Buy( Sell( OrderModify(";
    OrderCalcProfit(ORDER_TYPE_BUY, symbol, volume, open, close, result);
    OrderCalcMargin(ORDER_TYPE_SELL, symbol, volume, price, result);
    """

    assert forbidden_trade_api_matches(source) == ()


def test_safety_scan_rejects_oversized_probe(tmp_path: Path) -> None:
    path = tmp_path / "probe.mq5"
    path.write_text(" " * 1_000_001, encoding="utf-8")

    with pytest.raises(ValueError, match="one-megabyte"):
        scan_read_only_probe(path)
