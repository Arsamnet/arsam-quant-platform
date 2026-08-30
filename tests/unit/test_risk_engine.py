"""Strong example- and property-based coverage for fail-closed risk rules."""

from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from hypothesis import given
from hypothesis import strategies as st

from fx_platform.domain.advisory import AiAssessmentStatus
from fx_platform.domain.common import TradeSide, TradingMode
from fx_platform.domain.economic import EconomicEvent, EventImportance
from fx_platform.domain.risk import RiskEngine, RiskLimits, RiskRejection
from tests.helpers import (
    NOW,
    make_account,
    make_assessment,
    make_market,
    make_signal,
)

RISK_ID = UUID("50000000-0000-4000-8000-000000000005")


def _engine(**changes: object) -> RiskEngine:
    values: dict[str, object] = {"allowed_symbols": frozenset({"EURUSD"})}
    values.update(changes)
    return RiskEngine(RiskLimits(**values))


def _evaluate(
    engine: RiskEngine | None = None,
    *,
    trading_mode: TradingMode = TradingMode.PAPER,
    market: object | None = None,
    account: object | None = None,
    signal: object | None = None,
    assessment: object | None = None,
    events: tuple[EconomicEvent, ...] = (),
    calendar_available: bool = False,
):
    return (engine or _engine()).evaluate(
        risk_decision_id=RISK_ID,
        evaluated_at=NOW,
        trading_mode=trading_mode,
        market=market or make_market(),
        account=account or make_account(),
        signal=signal or make_signal(),
        ai_assessment=assessment or make_assessment(),
        economic_events=events,
        calendar_available=calendar_available,
    )


def test_safe_paper_candidate_is_approved_with_exact_monetary_risk() -> None:
    decision = _evaluate()

    assert decision.approved
    assert decision.reasons == ()
    assert decision.calculated_risk_amount == Decimal(1)
    assert decision.maximum_risk_amount == Decimal(100)


def test_non_paper_mode_and_unknown_symbol_are_rejected() -> None:
    decision = _evaluate(
        trading_mode=TradingMode.LIVE,
        market=make_market(symbol="GBPUSD"),
        signal=make_signal(symbol="GBPUSD"),
    )

    assert not decision.approved
    assert RiskRejection.NON_PAPER_MODE in decision.reasons
    assert RiskRejection.UNKNOWN_SYMBOL in decision.reasons


def test_mismatched_market_snapshot_is_rejected() -> None:
    signal = make_signal()
    mismatched = type(signal)(
        signal_id=signal.signal_id,
        market_snapshot_id=uuid4(),
        strategy_name=signal.strategy_name,
        strategy_version=signal.strategy_version,
        created_at=signal.created_at,
        symbol=signal.symbol,
        side=signal.side,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        volume=signal.volume,
    )

    assert RiskRejection.MARKET_SNAPSHOT_MISMATCH in _evaluate(signal=mismatched).reasons


def test_stale_and_future_state_fail_closed() -> None:
    stale = NOW - timedelta(minutes=2)
    future = NOW + timedelta(seconds=3)

    stale_decision = _evaluate(
        market=make_market(observed_at=stale),
        account=make_account(observed_at=stale),
        signal=make_signal(created_at=stale),
    )
    future_decision = _evaluate(
        market=make_market(observed_at=future),
        account=make_account(observed_at=future),
        signal=make_signal(created_at=future),
    )

    assert {
        RiskRejection.MARKET_DATA_STALE,
        RiskRejection.ACCOUNT_DATA_STALE,
        RiskRejection.SIGNAL_STALE,
    }.issubset(stale_decision.reasons)
    assert {
        RiskRejection.MARKET_DATA_IN_FUTURE,
        RiskRejection.ACCOUNT_DATA_IN_FUTURE,
        RiskRejection.SIGNAL_IN_FUTURE,
    }.issubset(future_decision.reasons)


def test_spread_missing_stop_and_wrong_side_stop_are_rejected() -> None:
    wide_market = make_market(ask=Decimal("1.1010"))
    missing_stop = _evaluate(market=wide_market, signal=make_signal(stop_loss=None))
    wrong_stop = _evaluate(signal=make_signal(stop_loss=Decimal("1.1003")))

    assert RiskRejection.SPREAD_TOO_WIDE in missing_stop.reasons
    assert RiskRejection.MISSING_STOP_LOSS in missing_stop.reasons
    assert missing_stop.calculated_risk_amount is None
    assert RiskRejection.INVALID_STOP_LOSS in wrong_stop.reasons


def test_sell_stop_must_be_above_entry() -> None:
    decision = _evaluate(
        signal=make_signal(
            side=TradeSide.SELL,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0999"),
        )
    )

    assert RiskRejection.INVALID_STOP_LOSS in decision.reasons


def test_position_and_daily_loss_limits_are_inclusive() -> None:
    decision = _evaluate(
        account=make_account(open_position_count=3, daily_realized_pnl=Decimal(-200))
    )

    assert RiskRejection.POSITION_LIMIT_EXCEEDED in decision.reasons
    assert RiskRejection.DAILY_LOSS_LIMIT_EXCEEDED in decision.reasons


def test_unavailable_or_invalid_ai_always_rejects() -> None:
    for status in (AiAssessmentStatus.UNAVAILABLE, AiAssessmentStatus.INVALID):
        decision = _evaluate(assessment=make_assessment(status=status))
        assert RiskRejection.AI_REQUIRED in decision.reasons


def test_required_ai_rejects_disabled_and_direction_conflict() -> None:
    required_engine = _engine(ai_required=True)

    disabled = _evaluate(required_engine)
    conflict = _evaluate(
        required_engine,
        assessment=make_assessment(
            status=AiAssessmentStatus.AVAILABLE,
            direction=TradeSide.SELL,
        ),
    )

    assert RiskRejection.AI_REQUIRED in disabled.reasons
    assert RiskRejection.AI_DIRECTION_CONFLICT in conflict.reasons


def test_assessment_for_another_signal_is_rejected() -> None:
    decision = _evaluate(assessment=make_assessment(signal_id=uuid4()))

    assert RiskRejection.AI_REQUIRED in decision.reasons


def test_high_impact_relevant_event_blocks_during_blackout() -> None:
    relevant_event = EconomicEvent(
        event_id=uuid4(),
        name="US CPI",
        scheduled_at=NOW + timedelta(minutes=5),
        importance=EventImportance.HIGH,
        currencies=frozenset({"USD"}),
        source_version="fixture-v1",
    )

    decision = _evaluate(events=(relevant_event,), calendar_available=True)

    assert RiskRejection.HIGH_IMPACT_EVENT_BLACKOUT in decision.reasons


def test_low_impact_or_irrelevant_events_do_not_block() -> None:
    events = (
        EconomicEvent(
            event_id=uuid4(),
            name="Minor USD event",
            scheduled_at=NOW,
            importance=EventImportance.LOW,
            currencies=frozenset({"USD"}),
            source_version="fixture-v1",
        ),
        EconomicEvent(
            event_id=uuid4(),
            name="High CAD event",
            scheduled_at=NOW,
            importance=EventImportance.HIGH,
            currencies=frozenset({"CAD"}),
            source_version="fixture-v1",
        ),
    )

    assert _evaluate(events=events, calendar_available=True).approved


def test_required_calendar_unavailable_fails_closed() -> None:
    decision = _evaluate(_engine(economic_calendar_required=True))

    assert RiskRejection.CALENDAR_REQUIRED in decision.reasons


def test_trade_risk_over_account_budget_is_rejected() -> None:
    decision = _evaluate(signal=make_signal(stop_loss=Decimal("1.0000"), volume=Decimal("0.10")))

    assert decision.calculated_risk_amount == Decimal(1002)
    assert RiskRejection.TRADE_RISK_LIMIT_EXCEEDED in decision.reasons


@given(
    volume=st.decimals(
        min_value=Decimal("0.1001"),
        max_value=Decimal(100),
        allow_nan=False,
        allow_infinity=False,
        places=4,
    )
)
def test_property_position_size_never_exceeds_configured_maximum(volume: Decimal) -> None:
    decision = _evaluate(signal=make_signal(volume=volume))

    assert not decision.approved
    assert RiskRejection.VOLUME_LIMIT_EXCEEDED in decision.reasons


@given(
    volume=st.decimals(
        min_value=Decimal(-10),
        max_value=Decimal(0),
        allow_nan=False,
        allow_infinity=False,
        places=4,
    )
)
def test_property_non_positive_volume_cannot_be_approved(volume: Decimal) -> None:
    decision = _evaluate(signal=make_signal(volume=volume))

    assert not decision.approved
    assert RiskRejection.INVALID_VOLUME in decision.reasons
    assert decision.calculated_risk_amount is None


def test_risk_limit_configuration_rejects_unsafe_values() -> None:
    invalid_values = (
        {"allowed_symbols": frozenset()},
        {"allowed_symbols": frozenset({"eurusd"})},
        {"allowed_symbols": frozenset({"EURUSD"}), "max_volume": Decimal(0)},
        {"allowed_symbols": frozenset({"EURUSD"}), "max_open_positions": 0},
        {
            "allowed_symbols": frozenset({"EURUSD"}),
            "max_trade_risk_fraction": Decimal("1.1"),
        },
        {
            "allowed_symbols": frozenset({"EURUSD"}),
            "max_market_age": timedelta(seconds=-1),
        },
    )

    for values in invalid_values:
        try:
            RiskLimits(**values)
        except ValueError:
            continue
        raise AssertionError(f"unsafe limits accepted: {values}")
