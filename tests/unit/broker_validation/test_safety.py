"""Defense-in-depth read-only MQL5 lexical safety checks."""

from pathlib import Path

import pytest

from fx_platform.broker_validation.safety import (
    forbidden_trade_api_matches,
    scan_read_only_probe,
)

PROBE_PATH = Path(__file__).parents[3] / "mt5" / "metadata_probe" / "ReadOnlyMetadataProbe.mq5"


def test_repository_read_only_probe_contains_no_forbidden_trade_api() -> None:
    assert scan_read_only_probe(PROBE_PATH) == ()


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
