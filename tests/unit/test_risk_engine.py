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
    make_conversion_rate,
    make_market,
    make_signal,
    make_specification,
)

RISK_ID = UUID("50000000-0000-4000-8000-000000000005")
_DEFAULT_SPECIFICATION = object()


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
    specification: object | None = _DEFAULT_SPECIFICATION,
    conversion_rates: tuple[object, ...] = (),
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
        symbol_specification=(
            make_specification() if specification is _DEFAULT_SPECIFICATION else specification
        ),
        conversion_rates=conversion_rates,
    )


def test_safe_paper_candidate_is_approved_with_exact_monetary_risk() -> None:
    decision = _evaluate()

    assert decision.approved
    assert decision.reasons == ()
    assert decision.calculated_risk_amount == Decimal(1)
    assert decision.maximum_risk_amount == Decimal(100)
    assert decision.maximum_daily_loss_amount == Decimal(200)


def test_non_paper_mode_is_rejected() -> None:
    decision = _evaluate(
        trading_mode=TradingMode.LIVE,
    )

    assert not decision.approved
    assert RiskRejection.NON_PAPER_MODE in decision.reasons


def test_risk_engine_independently_rejects_unknown_symbol() -> None:
    decision = _evaluate(
        market=make_market(symbol="XAUUSD"),
        signal=make_signal(symbol="XAUUSD"),
        specification=None,
    )

    assert RiskRejection.UNKNOWN_SYMBOL in decision.reasons


def test_allowed_symbol_without_specification_fails_closed() -> None:
    decision = _evaluate(specification=None)

    assert RiskRejection.SYMBOL_SPECIFICATION_UNAVAILABLE in decision.reasons
    assert decision.calculated_risk_amount is None


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


def test_daily_loss_boundary_uses_relative_limit_and_optional_hard_cap() -> None:
    just_below = _evaluate(account=make_account(daily_realized_pnl=Decimal("-199.99")))
    exactly_at = _evaluate(account=make_account(daily_realized_pnl=Decimal(-200)))
    beyond = _evaluate(account=make_account(daily_realized_pnl=Decimal("-200.01")))

    assert RiskRejection.DAILY_LOSS_LIMIT_EXCEEDED not in just_below.reasons
    assert RiskRejection.DAILY_LOSS_LIMIT_EXCEEDED in exactly_at.reasons
    assert RiskRejection.DAILY_LOSS_LIMIT_EXCEEDED in beyond.reasons
    assert exactly_at.maximum_daily_loss_amount == Decimal(200)


@given(
    balance=st.decimals(
        min_value=Decimal(100),
        max_value=Decimal(1000000),
        allow_nan=False,
        allow_infinity=False,
        places=2,
    )
)
def test_property_relative_daily_loss_scales_with_balance(balance: Decimal) -> None:
    engine = _engine(max_daily_loss_absolute_cap=None)
    limit = balance * Decimal("0.02")

    below = _evaluate(
        engine,
        account=make_account(
            balance=balance,
            equity=balance,
            daily_realized_pnl=-(limit - Decimal("0.01")),
        ),
    )
    at_limit = _evaluate(
        engine,
        account=make_account(
            balance=balance,
            equity=balance,
            daily_realized_pnl=-limit,
        ),
    )

    assert RiskRejection.DAILY_LOSS_LIMIT_EXCEEDED not in below.reasons
    assert RiskRejection.DAILY_LOSS_LIMIT_EXCEEDED in at_limit.reasons
    assert at_limit.maximum_daily_loss_amount == limit


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


def test_required_ai_rejects_neutral_low_confidence_and_high_uncertainty() -> None:
    required_engine = _engine(ai_required=True)

    neutral = _evaluate(
        required_engine,
        assessment=make_assessment(
            status=AiAssessmentStatus.AVAILABLE,
            direction=None,
        ),
    )
    low_confidence = _evaluate(
        required_engine,
        assessment=make_assessment(
            status=AiAssessmentStatus.AVAILABLE,
            direction=TradeSide.BUY,
            confidence=Decimal("0.59"),
            uncertainty=Decimal("0.25"),
        ),
    )
    high_uncertainty = _evaluate(
        required_engine,
        assessment=make_assessment(
            status=AiAssessmentStatus.AVAILABLE,
            direction=TradeSide.BUY,
            confidence=Decimal("0.75"),
            uncertainty=Decimal("0.51"),
        ),
    )

    assert RiskRejection.AI_DIRECTION_REQUIRED in neutral.reasons
    assert RiskRejection.AI_CONFIDENCE_TOO_LOW in low_confidence.reasons
    assert RiskRejection.AI_UNCERTAINTY_TOO_HIGH in high_uncertainty.reasons


def test_required_ai_accepts_reviewed_quality_boundary() -> None:
    decision = _evaluate(
        _engine(ai_required=True),
        assessment=make_assessment(
            status=AiAssessmentStatus.AVAILABLE,
            direction=TradeSide.BUY,
            confidence=Decimal("0.60"),
            uncertainty=Decimal("0.50"),
        ),
    )

    assert decision.approved


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


def test_missing_spread_policy_fails_closed() -> None:
    decision = _evaluate(specification=make_specification(max_spread_ticks=None))

    assert RiskRejection.SPREAD_POLICY_UNAVAILABLE in decision.reasons


def test_symbol_spread_limit_is_interpreted_in_that_symbols_ticks() -> None:
    specification = make_specification(
        symbol="USDJPY",
        base_currency="USD",
        quote_currency="JPY",
        tick_size=Decimal("0.001"),
        tick_value=Decimal(100),
        tick_value_currency="JPY",
    )
    engine = _engine(allowed_symbols=frozenset({"USDJPY"}))

    accepted = _evaluate(
        engine,
        market=make_market(symbol="USDJPY", bid=Decimal(150), ask=Decimal("150.050")),
        signal=make_signal(symbol="USDJPY"),
        specification=specification,
        conversion_rates=(make_conversion_rate(),),
    )
    rejected = _evaluate(
        engine,
        market=make_market(symbol="USDJPY", bid=Decimal(150), ask=Decimal("150.051")),
        signal=make_signal(symbol="USDJPY"),
        specification=specification,
        conversion_rates=(make_conversion_rate(),),
    )

    assert RiskRejection.SPREAD_TOO_WIDE not in accepted.reasons
    assert RiskRejection.SPREAD_TOO_WIDE in rejected.reasons


def test_symbol_volume_grid_is_enforced() -> None:
    below = _evaluate(signal=make_signal(volume=Decimal("0.001")))
    off_step = _evaluate(signal=make_signal(volume=Decimal("0.015")))

    assert RiskRejection.VOLUME_BELOW_MINIMUM in below.reasons
    assert RiskRejection.VOLUME_STEP_MISMATCH in off_step.reasons


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
        {
            "allowed_symbols": frozenset({"EURUSD"}),
            "max_daily_loss_fraction": Decimal(0),
        },
        {
            "allowed_symbols": frozenset({"EURUSD"}),
            "max_daily_loss_absolute_cap": Decimal(0),
        },
        {"allowed_symbols": frozenset({"EURUSD"}), "max_open_positions": 0},
        {
            "allowed_symbols": frozenset({"EURUSD"}),
            "max_trade_risk_fraction": Decimal("1.1"),
        },
        {
            "allowed_symbols": frozenset({"EURUSD"}),
            "max_market_age": timedelta(seconds=-1),
        },
        {
            "allowed_symbols": frozenset({"EURUSD"}),
            "ai_min_confidence": Decimal("1.01"),
        },
        {
            "allowed_symbols": frozenset({"EURUSD"}),
            "ai_max_uncertainty": Decimal("-0.01"),
        },
    )

    for values in invalid_values:
        try:
            RiskLimits(**values)
        except ValueError:
            continue
        raise AssertionError(f"unsafe limits accepted: {values}")
