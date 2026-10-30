"""Static safety checks for the read-only autonomous MT5 snapshot probe."""

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[2]
AUTONOMOUS_PROBE = REPOSITORY_ROOT / "mt5" / "autonomous_probe" / "ArsamAutonomousSnapshotProbe.mq5"


def test_autonomous_probe_contains_no_trade_mutation_api() -> None:
    source = AUTONOMOUS_PROBE.read_text(encoding="utf-8")

    forbidden = (
        "OrderSend(",
        "OrderSendAsync(",
        "CTrade",
        ".Buy(",
        ".Sell(",
        "PositionClose(",
        "OrderDelete(",
        "OrderModify(",
    )
    for token in forbidden:
        assert token not in source


def test_autonomous_probe_exports_required_fail_closed_inputs() -> None:
    source = AUTONOMOUS_PROBE.read_text(encoding="utf-8")

    normalized_source = source.replace(r"\"", '"')
    for field in (
        "balance",
        "equity",
        "daily_realized_pnl",
        "open_position_count",
        "bid",
        "ask",
        "previous_close",
        "decision_bar_time",
        "tick_age_seconds",
    ):
        assert f'"{field}"' in normalized_source

    assert "HistorySelect(" in source
    assert "SymbolInfoTick(" in source
    assert "EventSetTimer(" in source
    assert "PERIOD_M15" in source
