"""Static regression checks for the MQL5 OrderCheck success contract."""

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[2]
EXECUTION_GUARD = REPOSITORY_ROOT / "mt5" / "execution_guard" / "ArsamDemoExecutionGuard.mq5"


def test_ordercheck_accepts_zero_retcode_and_not_trade_retcode_done() -> None:
    source = EXECUTION_GUARD.read_text(encoding="utf-8")

    assert "check.retcode!=TRADE_RETCODE_DONE" not in source

    assert source.count("OrderCheck(request,check)") == 2
    assert source.count("check.retcode!=0") == 2

    assert "bool check_ok=OrderCheck(request,check);" in source
    assert "int check_error=GetLastError();" in source
    assert "if(!check_ok || check_error!=0 || check.retcode!=0)" in source

    assert "bool final_check_ok=OrderCheck(request,check);" in source
    assert "int final_check_error=GetLastError();" in source
    assert "if(!final_check_ok || final_check_error!=0 || check.retcode!=0)" in source


def test_ordercheck_failure_preserves_local_error_retcode_and_comment() -> None:
    source = EXECUTION_GUARD.read_text(encoding="utf-8")

    assert '"order_check_failed_local_"+' in source
    assert '"final_order_check_failed_local_"+' in source

    assert "IntegerToString(check_error)" in source
    assert "IntegerToString(final_check_error)" in source
    assert source.count("IntegerToString((int)check.retcode)") >= 2
    assert source.count("check.comment") >= 2


def test_stop_preflight_uses_position_trigger_side_for_initial_and_final_ticks() -> None:
    source = EXECUTION_GUARD.read_text(encoding="utf-8")

    assert 'double trigger_price=(work.side=="buy" ? tick.bid : tick.ask);' in source
    assert "work.stop_loss>=trigger_price" in source
    assert "work.take_profit<=trigger_price" in source
    assert "work.stop_loss<=trigger_price" in source
    assert "work.take_profit>=trigger_price" in source
    assert "MathAbs(trigger_price-work.stop_loss)<minimum_distance" in source
    assert "MathAbs(work.take_profit-trigger_price)<minimum_distance" in source
    assert source.count("ValidateStopsForTick(work,") == 2
    assert "if(!ValidateStopsForTick(work,tick,reason))" in source
    assert "if(!ValidateStopsForTick(work,final_tick,reason))" in source


def test_market_request_price_remains_on_entry_side_without_send_retry() -> None:
    source = EXECUTION_GUARD.read_text(encoding="utf-8")

    assert 'request.price=(work.side=="buy" ? tick.ask : tick.bid);' in source
    assert 'request.price=(work.side=="buy" ? final_tick.ask : final_tick.bid);' in source
    assert source.count("OrderCheck(request,check)") == 2
    assert source.count("OrderSend(request,result)") == 1
    assert "OrderSendAsync" not in source
