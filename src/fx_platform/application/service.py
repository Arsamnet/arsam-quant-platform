"""Deterministic decision workflow with fail-closed execution boundaries."""

import hashlib
from datetime import datetime, timedelta
from uuid import UUID, uuid5

from fx_platform.application.models import (
    AuditStage,
    DecisionAuditRecord,
    DecisionCommand,
    DecisionOutcome,
    DecisionOutcomeStatus,
)
from fx_platform.application.ports import (
    AiAdvisor,
    AuditRepository,
    Clock,
    EconomicCalendarProvider,
    ExecutionAdapter,
    StrategyEvaluator,
    SymbolSpecificationProvider,
)
from fx_platform.domain.common import TradingMode
from fx_platform.domain.execution import ExecutionIntent, ExecutionStatus, OrderType
from fx_platform.domain.market import SymbolSpecification
from fx_platform.domain.risk import RiskEngine
from fx_platform.domain.strategy import SignalCandidate

_ID_NAMESPACE = UUID("f344fe7f-5286-4ff9-a0aa-7217f58e172c")


def _derived_id(request_id: UUID, purpose: str) -> UUID:
    return uuid5(_ID_NAMESPACE, f"{request_id}:{purpose}")


def _fingerprint(*values: object) -> str:
    canonical = "\x1f".join(str(value) for value in values).encode()
    return hashlib.sha256(canonical).hexdigest()


def _request_fingerprint(command: DecisionCommand) -> str:
    conversion_values = tuple(
        value
        for rate in command.conversion_rates
        for value in (
            rate.source_currency,
            rate.target_currency,
            rate.rate,
            rate.observed_at.isoformat(),
        )
    )
    return _fingerprint(
        command.schema_version,
        command.request_id,
        command.request_timestamp.isoformat(),
        command.nonce,
        command.node_id,
        command.market.snapshot_id,
        command.market.symbol,
        command.market.observed_at.isoformat(),
        command.market.bid,
        command.market.ask,
        command.market.previous_close,
        command.account.account_id,
        command.account.observed_at.isoformat(),
        command.account.balance,
        command.account.equity,
        command.account.daily_realized_pnl,
        command.account.open_position_count,
        command.account.currency,
        *conversion_values,
    )


class DecisionService:
    """Orchestrate one candidate signal without granting AI execution authority."""

    def __init__(
        self,
        *,
        node_id: str,
        trading_mode: TradingMode,
        clock: Clock,
        strategy: StrategyEvaluator,
        symbol_specifications: SymbolSpecificationProvider,
        ai_advisor: AiAdvisor,
        risk_engine: RiskEngine,
        calendar: EconomicCalendarProvider,
        executor: ExecutionAdapter,
        audit_repository: AuditRepository,
        intent_ttl: timedelta = timedelta(seconds=10),
        max_request_age: timedelta = timedelta(seconds=30),
        max_future_skew: timedelta = timedelta(seconds=2),
    ) -> None:
        if trading_mode is TradingMode.LIVE:
            raise ValueError("DecisionService forbids live mode")
        if not node_id:
            raise ValueError("node_id must not be empty")
        self._node_id = node_id
        self._trading_mode = trading_mode
        self._clock = clock
        self._strategy = strategy
        self._symbol_specifications = symbol_specifications
        self._ai_advisor = ai_advisor
        self._risk_engine = risk_engine
        self._calendar = calendar
        self._executor = executor
        self._audit_repository = audit_repository
        self._intent_ttl = intent_ttl
        self._max_request_age = max_request_age
        self._max_future_skew = max_future_skew

    def decide(self, command: DecisionCommand) -> DecisionOutcome:
        """Run the vertical slice; any unhandled infrastructure error propagates as no approval."""
        existing = self._audit_repository.get(command.request_id)
        nonce_record = self._audit_repository.get_by_nonce(command.nonce)
        if existing is not None or nonce_record is not None:
            prior = existing if existing is not None else nonce_record
            if prior is None:
                raise RuntimeError("duplicate lookup returned inconsistent state")
            return DecisionOutcome(
                request_id=command.request_id,
                status=DecisionOutcomeStatus.DUPLICATE,
                signal_id=prior.signal_id,
                risk_decision_id=prior.risk_decision_id,
                execution_id=prior.execution_id,
                execution_status=ExecutionStatus.DUPLICATE,
                reasons=("duplicate_request_or_nonce",),
            )

        now = self._clock.now()
        if command.node_id != self._node_id:
            self._save_rejected_without_signal(command, now, "node_id_mismatch")
            return DecisionOutcome(
                request_id=command.request_id,
                status=DecisionOutcomeStatus.RISK_REJECTED,
                signal_id=None,
                risk_decision_id=None,
                execution_id=None,
                execution_status=None,
                reasons=("node_id_mismatch",),
            )
        age_reason = self._request_age_reason(command, now)
        if age_reason is not None:
            self._save_rejected_without_signal(command, now, age_reason)
            return DecisionOutcome(
                request_id=command.request_id,
                status=DecisionOutcomeStatus.RISK_REJECTED,
                signal_id=None,
                risk_decision_id=None,
                execution_id=None,
                execution_status=None,
                reasons=(age_reason,),
            )

        symbol_specification = self._symbol_specifications.get(command.market.symbol)
        if symbol_specification is None:
            self._save_rejected_without_signal(command, now, "unknown_symbol")
            return DecisionOutcome(
                request_id=command.request_id,
                status=DecisionOutcomeStatus.RISK_REJECTED,
                signal_id=None,
                risk_decision_id=None,
                execution_id=None,
                execution_status=None,
                reasons=("unknown_symbol",),
            )

        signal_id = _derived_id(command.request_id, "signal")
        strategy_decision = self._strategy.evaluate(
            command.market,
            signal_id=signal_id,
            evaluated_at=now,
        )
        if strategy_decision.candidate is None:
            reasons = strategy_decision.reasons
            self._audit_repository.save(
                DecisionAuditRecord(
                    decision_id=command.request_id,
                    nonce=command.nonce,
                    occurred_at=now,
                    stage=AuditStage.REJECTED,
                    node_id=command.node_id,
                    market_snapshot_id=command.market.snapshot_id,
                    symbol=command.market.symbol,
                    strategy_name=strategy_decision.strategy_name,
                    strategy_version=strategy_decision.strategy_version,
                    signal_id=None,
                    ai_status="not_requested",
                    risk_decision_id=None,
                    risk_approved=False,
                    risk_reasons=reasons,
                    execution_id=None,
                    execution_status=None,
                )
            )
            return DecisionOutcome(
                request_id=command.request_id,
                status=DecisionOutcomeStatus.NO_SIGNAL,
                signal_id=None,
                risk_decision_id=None,
                execution_id=None,
                execution_status=None,
                reasons=reasons,
            )

        return self._evaluate_candidate(
            command,
            now,
            strategy_decision.candidate,
            symbol_specification,
        )

    def _evaluate_candidate(
        self,
        command: DecisionCommand,
        now: datetime,
        signal: SignalCandidate,
        symbol_specification: SymbolSpecification,
    ) -> DecisionOutcome:
        # Kept as a separate step so every external read finishes before intent persistence.
        assessment = self._ai_advisor.assess(
            assessment_id=_derived_id(command.request_id, "ai"),
            evaluated_at=now,
            market=command.market,
            signal=signal,
        )
        calendar = self._calendar.events_for(
            symbol=signal.symbol,
            window_start=now - timedelta(minutes=15),
            window_end=now + timedelta(minutes=15),
        )
        risk_decision = self._risk_engine.evaluate(
            risk_decision_id=_derived_id(command.request_id, "risk"),
            evaluated_at=now,
            trading_mode=self._trading_mode,
            market=command.market,
            account=command.account,
            signal=signal,
            ai_assessment=assessment,
            economic_events=calendar.events,
            calendar_available=calendar.available,
            symbol_specification=symbol_specification,
            conversion_rates=command.conversion_rates,
        )
        if not risk_decision.approved:
            reasons = tuple(reason.value for reason in risk_decision.reasons)
            self._audit_repository.save(
                self._audit_record(
                    command=command,
                    now=now,
                    stage=AuditStage.REJECTED,
                    signal=signal,
                    ai_status=assessment.status.value,
                    risk_decision_id=risk_decision.risk_decision_id,
                    risk_approved=False,
                    risk_reasons=reasons,
                    execution_id=None,
                    execution_status=None,
                )
            )
            return DecisionOutcome(
                request_id=command.request_id,
                status=DecisionOutcomeStatus.RISK_REJECTED,
                signal_id=signal.signal_id,
                risk_decision_id=risk_decision.risk_decision_id,
                execution_id=None,
                execution_status=None,
                reasons=reasons,
            )

        intent = self._approved_intent(
            command,
            now,
            signal,
            risk_decision.risk_decision_id,
            symbol_specification,
        )
        self._audit_repository.save(
            self._audit_record(
                command=command,
                now=now,
                stage=AuditStage.INTENT_CREATED,
                signal=signal,
                ai_status=assessment.status.value,
                risk_decision_id=risk_decision.risk_decision_id,
                risk_approved=True,
                risk_reasons=(),
                execution_id=intent.execution_id,
                execution_status=None,
            )
        )
        execution_result = self._executor.execute(intent)
        final_stage = (
            AuditStage.OUTBOXED
            if execution_result.status is ExecutionStatus.PENDING
            else AuditStage.COMPLETED
        )
        completed_at = self._clock.now()
        self._audit_repository.save(
            self._audit_record(
                command=command,
                now=completed_at,
                stage=final_stage,
                signal=signal,
                ai_status=assessment.status.value,
                risk_decision_id=risk_decision.risk_decision_id,
                risk_approved=True,
                risk_reasons=(),
                execution_id=intent.execution_id,
                execution_status=execution_result.status.value,
            )
        )
        if execution_result.status is ExecutionStatus.DUPLICATE:
            outcome_status = DecisionOutcomeStatus.DUPLICATE
        elif execution_result.status is ExecutionStatus.PENDING:
            outcome_status = DecisionOutcomeStatus.DEMO_QUEUED
        elif execution_result.status is ExecutionStatus.PAPER_FILLED:
            outcome_status = DecisionOutcomeStatus.PAPER_EXECUTED
        else:
            outcome_status = DecisionOutcomeStatus.EXECUTION_REJECTED
        return DecisionOutcome(
            request_id=command.request_id,
            status=outcome_status,
            signal_id=signal.signal_id,
            risk_decision_id=risk_decision.risk_decision_id,
            execution_id=intent.execution_id,
            execution_status=execution_result.status,
            reasons=()
            if execution_result.status in {ExecutionStatus.PAPER_FILLED, ExecutionStatus.PENDING}
            else (execution_result.message,),
        )

    def _request_age_reason(self, command: DecisionCommand, now: datetime) -> str | None:
        if now - command.request_timestamp > self._max_request_age:
            return "request_stale"
        if command.request_timestamp - now > self._max_future_skew:
            return "request_timestamp_in_future"
        return None

    def _save_rejected_without_signal(
        self,
        command: DecisionCommand,
        now: datetime,
        reason: str,
    ) -> None:
        self._audit_repository.save(
            DecisionAuditRecord(
                decision_id=command.request_id,
                nonce=command.nonce,
                occurred_at=now,
                stage=AuditStage.REJECTED,
                node_id=command.node_id,
                market_snapshot_id=command.market.snapshot_id,
                symbol=command.market.symbol,
                strategy_name=self._strategy.name,
                strategy_version=self._strategy.version,
                signal_id=None,
                ai_status="not_requested",
                risk_decision_id=None,
                risk_approved=False,
                risk_reasons=(reason,),
                execution_id=None,
                execution_status=None,
            )
        )

    def _approved_intent(
        self,
        command: DecisionCommand,
        now: datetime,
        signal: SignalCandidate,
        risk_decision_id: UUID,
        symbol_specification: SymbolSpecification,
    ) -> ExecutionIntent:
        if signal.stop_loss is None:
            raise RuntimeError("approved signal unexpectedly has no stop loss")
        maximum_spread = symbol_specification.maximum_spread
        if maximum_spread is None:
            raise RuntimeError("approved signal unexpectedly has no spread policy")
        return ExecutionIntent(
            schema_version="1.0",
            execution_id=_derived_id(command.request_id, "execution"),
            intent_id=_derived_id(command.request_id, "intent"),
            request_id=command.request_id,
            signal_id=signal.signal_id,
            risk_decision_id=risk_decision_id,
            created_at=now,
            expires_at=now + self._intent_ttl,
            node_id=self._node_id,
            symbol=signal.symbol,
            side=signal.side,
            order_type=OrderType.MARKET,
            volume=signal.volume,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            maximum_spread=maximum_spread,
            risk_fingerprint=_fingerprint(
                risk_decision_id,
                signal.signal_id,
                signal.symbol,
                signal.side.value,
                signal.volume,
                signal.stop_loss,
                signal.take_profit,
            ),
            request_fingerprint=_request_fingerprint(command),
            nonce=command.nonce,
            strategy_name=signal.strategy_name,
            strategy_version=signal.strategy_version,
            trading_mode=self._trading_mode,
        )

    def _audit_record(
        self,
        *,
        command: DecisionCommand,
        now: datetime,
        stage: AuditStage,
        signal: SignalCandidate,
        ai_status: str,
        risk_decision_id: UUID,
        risk_approved: bool,
        risk_reasons: tuple[str, ...],
        execution_id: UUID | None,
        execution_status: str | None,
    ) -> DecisionAuditRecord:
        return DecisionAuditRecord(
            decision_id=command.request_id,
            nonce=command.nonce,
            occurred_at=now,
            stage=stage,
            node_id=command.node_id,
            market_snapshot_id=command.market.snapshot_id,
            symbol=command.market.symbol,
            strategy_name=signal.strategy_name,
            strategy_version=signal.strategy_version,
            signal_id=signal.signal_id,
            ai_status=ai_status,
            risk_decision_id=risk_decision_id,
            risk_approved=risk_approved,
            risk_reasons=risk_reasons,
            execution_id=execution_id,
            execution_status=execution_status,
        )
