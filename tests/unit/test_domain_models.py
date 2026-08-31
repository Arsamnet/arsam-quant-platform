"""Value-object invariants at financial and temporal boundaries."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from fx_platform.domain.advisory import AiAssessment, AiAssessmentStatus
from fx_platform.domain.common import TradeSide, TradingMode, require_utc
from fx_platform.domain.economic import EconomicEvent, EventImportance
from fx_platform.domain.execution import ExecutionIntent, ExecutionResult, ExecutionStatus
from fx_platform.domain.market import (
    AccountSnapshot,
    CurrencyConversionFailure,
    CurrencyConversionRate,
    CurrencyConversionResult,
    MarketSnapshot,
    convert_currency,
)
from fx_platform.domain.risk import RiskDecision, RiskRejection
from fx_platform.domain.strategy import SignalCandidate, StrategyDecision
from tests.helpers import (
    ASSESSMENT_ID,
    MARKET_ID,
    NOW,
    SIGNAL_ID,
    make_account,
    make_market,
    make_specification,
)


def test_market_snapshot_exposes_exact_spread_and_midpoint() -> None:
    market = make_market()

    assert market.spread == Decimal("0.0002")
    assert market.mid_price == Decimal("1.1001")


def test_symbol_specification_exposes_tick_spread_and_volume_grid() -> None:
    specification = make_specification()

    assert specification.maximum_spread == Decimal("0.00050")
    assert specification.accepts_volume(Decimal("0.01"))
    assert specification.accepts_volume(Decimal("0.10"))
    assert not specification.accepts_volume(Decimal("0.015"))
    assert not specification.accepts_volume(Decimal("0.11"))


@pytest.mark.parametrize(
    "changes",
    [
        {"symbol": "eurusd"},
        {"contract_size": Decimal(0)},
        {"volume_min": Decimal("0.11")},
        {"price_digits": -1},
        {"max_spread_ticks": -1},
    ],
)
def test_symbol_specification_rejects_invalid_metadata(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(make_specification(), **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"source_currency": "jpy"},
        {"target_currency": "JPY"},
        {"rate": Decimal(0)},
        {"observed_at": NOW.replace(tzinfo=None)},
    ],
)
def test_conversion_rate_rejects_invalid_state(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "source_currency": "JPY",
        "target_currency": "USD",
        "rate": Decimal("0.0067"),
        "observed_at": NOW,
    }
    values.update(changes)

    with pytest.raises(ValueError):
        CurrencyConversionRate(**values)


def test_generic_currency_conversion_validates_amount_and_result_shape() -> None:
    identity = convert_currency(
        amount=Decimal(0),
        source_currency="USD",
        target_currency="USD",
        conversion_rates=(),
        evaluated_at=NOW,
        max_conversion_age=timedelta(seconds=30),
        max_future_skew=timedelta(0),
    )

    assert identity.amount == Decimal(0)
    with pytest.raises(ValueError, match="negative"):
        convert_currency(
            amount=Decimal(-1),
            source_currency="USD",
            target_currency="USD",
            conversion_rates=(),
            evaluated_at=NOW,
            max_conversion_age=timedelta(seconds=30),
            max_future_skew=timedelta(0),
        )
    with pytest.raises(ValueError, match="exactly one"):
        CurrencyConversionResult(amount=None, failure=None)
    assert (
        CurrencyConversionResult(
            amount=None,
            failure=CurrencyConversionFailure.CONVERSION_RATE_UNAVAILABLE,
        ).failure
        is CurrencyConversionFailure.CONVERSION_RATE_UNAVAILABLE
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"symbol": "eurusd"}, "uppercase"),
        ({"bid": Decimal(0)}, "greater than zero"),
        ({"ask": Decimal("1.0"), "bid": Decimal("1.1")}, "ask must"),
        ({"previous_close": Decimal("NaN")}, "finite"),
        ({"observed_at": NOW.replace(tzinfo=None)}, "UTC"),
    ],
)
def test_market_snapshot_rejects_invalid_state(
    changes: dict[str, object],
    message: str,
) -> None:
    values: dict[str, object] = {
        "snapshot_id": MARKET_ID,
        "symbol": "EURUSD",
        "observed_at": NOW,
        "bid": Decimal("1.1000"),
        "ask": Decimal("1.1002"),
        "previous_close": Decimal("1.0990"),
    }
    values.update(changes)

    with pytest.raises(ValueError, match=message):
        MarketSnapshot(**values)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"account_id": ""}, "account_id"),
        ({"balance": Decimal(0)}, "greater than zero"),
        ({"equity": Decimal(-1)}, "negative"),
        ({"daily_realized_pnl": Decimal("Infinity")}, "finite"),
        ({"open_position_count": -1}, "negative"),
    ],
)
def test_account_snapshot_rejects_invalid_state(
    changes: dict[str, object],
    message: str,
) -> None:
    values: dict[str, object] = {
        "account_id": "paper-account",
        "observed_at": NOW,
        "balance": Decimal(10000),
        "equity": Decimal(10000),
        "daily_realized_pnl": Decimal(0),
        "open_position_count": 0,
    }
    values.update(changes)

    with pytest.raises(ValueError, match=message):
        AccountSnapshot(**values)


def test_signal_candidate_allows_missing_stop_only_for_risk_rejection() -> None:
    signal = SignalCandidate(
        signal_id=SIGNAL_ID,
        market_snapshot_id=MARKET_ID,
        strategy_name="fixture",
        strategy_version="1",
        created_at=NOW,
        symbol="EURUSD",
        side=TradeSide.BUY,
        entry_price=Decimal("1.1"),
        stop_loss=None,
        take_profit=None,
        volume=Decimal("0.01"),
    )

    assert signal.stop_loss is None


def test_strategy_decision_requires_reason_when_no_signal() -> None:
    with pytest.raises(ValueError, match="requires a reason"):
        StrategyDecision(
            strategy_name="fixture",
            strategy_version="1",
            evaluated_at=NOW,
            candidate=None,
            reasons=(),
        )


def test_ai_assessment_rejects_unbounded_confidence_and_tags() -> None:
    with pytest.raises(ValueError, match="confidence"):
        AiAssessment(
            assessment_id=ASSESSMENT_ID,
            signal_id=SIGNAL_ID,
            created_at=NOW,
            status=AiAssessmentStatus.AVAILABLE,
            direction_preference=None,
            confidence=Decimal("1.1"),
            market_regime="uncertain",
            uncertainty=Decimal(0),
            reasoning_tags=(),
        )


def test_economic_event_requires_utc_uppercase_point_in_time_data() -> None:
    event = EconomicEvent(
        event_id=uuid4(),
        name="CPI",
        scheduled_at=NOW,
        importance=EventImportance.HIGH,
        currencies=frozenset({"USD"}),
        source_version="fixture-v1",
        forecast=Decimal("2.1"),
        previous=Decimal("2.0"),
    )

    assert event.actual is None
    with pytest.raises(ValueError, match="uppercase"):
        EconomicEvent(
            event_id=uuid4(),
            name="CPI",
            scheduled_at=NOW,
            importance=EventImportance.HIGH,
            currencies=frozenset({"usd"}),
            source_version="fixture-v1",
        )


def _intent(**changes: object) -> ExecutionIntent:
    values: dict[str, object] = {
        "execution_id": uuid4(),
        "decision_id": uuid4(),
        "signal_id": SIGNAL_ID,
        "risk_decision_id": uuid4(),
        "created_at": NOW,
        "expires_at": NOW + timedelta(seconds=10),
        "node_id": "paper-node",
        "symbol": "EURUSD",
        "side": TradeSide.BUY,
        "volume": Decimal("0.01"),
        "entry_price": Decimal("1.1002"),
        "stop_loss": Decimal("1.0992"),
        "take_profit": Decimal("1.1022"),
        "trading_mode": TradingMode.PAPER,
    }
    values.update(changes)
    return ExecutionIntent(**values)


def test_execution_intent_is_paper_only_and_has_future_expiry() -> None:
    assert _intent().trading_mode is TradingMode.PAPER
    with pytest.raises(ValueError, match="paper"):
        _intent(trading_mode=TradingMode.LIVE)
    with pytest.raises(ValueError, match="later"):
        _intent(expires_at=NOW)


def test_execution_result_requires_message() -> None:
    with pytest.raises(ValueError, match="message"):
        ExecutionResult(
            execution_id=uuid4(),
            completed_at=NOW,
            status=ExecutionStatus.REJECTED,
            message="",
        )


def test_risk_decision_approval_and_reason_invariants() -> None:
    with pytest.raises(ValueError, match="approved decisions"):
        RiskDecision(
            risk_decision_id=uuid4(),
            signal_id=SIGNAL_ID,
            evaluated_at=NOW,
            approved=True,
            reasons=(RiskRejection.UNKNOWN_SYMBOL,),
            calculated_risk_amount=Decimal(1),
            maximum_risk_amount=Decimal(100),
            maximum_daily_loss_amount=Decimal(200),
        )


def test_require_utc_rejects_non_utc_offset() -> None:
    non_utc = datetime(2026, 8, 30, 15, 30, tzinfo=UTC) + timedelta(hours=0)
    require_utc(non_utc, "timestamp")
    assert make_account().observed_at.tzinfo is UTC
