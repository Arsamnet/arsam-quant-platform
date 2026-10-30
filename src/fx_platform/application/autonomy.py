"""Guarded autonomous DEMO orchestration above the existing decision service."""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid5

from fx_platform.application.models import DecisionCommand, DecisionOutcome, DecisionOutcomeStatus
from fx_platform.domain.market import (
    AccountSnapshot,
    BrokerFxQuote,
    InverseConversionRateDerivation,
    MarketSnapshot,
    derive_inverse_conversion_rate,
)

_AUTONOMY_NAMESPACE = UUID("6a12e493-4da9-4c6a-bcf3-4453fdc3f280")
_CURRENCY_CODE_LENGTH = 3
_BLOCKING_EXECUTION_STATUSES = frozenset(
    {
        "pending",
        "claimed",
        "submitted",
        "filled",
        "partially_filled",
        "unknown",
        "reconciliation_failed",
    }
)


class AutonomousSnapshotError(RuntimeError):
    """A market/account snapshot is unavailable or unsafe to use."""


@dataclass(frozen=True, slots=True, kw_only=True)
class AutonomousMarketObservation:
    """Fresh market state plus the bar identity used for autonomous deduplication."""

    market: MarketSnapshot
    decision_bar_time: datetime
    base_currency: str
    quote_currency: str

    def __post_init__(self) -> None:
        if self.decision_bar_time.tzinfo is None:
            raise ValueError("decision_bar_time must be timezone-aware")
        if (
            self.base_currency != self.base_currency.upper()
            or len(self.base_currency) != _CURRENCY_CODE_LENGTH
        ):
            raise ValueError("base_currency must be a three-letter uppercase code")
        if (
            self.quote_currency != self.quote_currency.upper()
            or len(self.quote_currency) != _CURRENCY_CODE_LENGTH
        ):
            raise ValueError("quote_currency must be a three-letter uppercase code")


@dataclass(frozen=True, slots=True, kw_only=True)
class AutonomousSnapshot:
    """One fail-closed account and multi-symbol observation from the local MT5 node."""

    acquired_at: datetime
    account: AccountSnapshot
    markets: tuple[AutonomousMarketObservation, ...]

    def __post_init__(self) -> None:
        if self.acquired_at.tzinfo is None:
            raise ValueError("acquired_at must be timezone-aware")
        if not self.markets:
            raise ValueError("autonomous snapshot must contain market observations")


class AutonomousSnapshotSource(Protocol):
    """Read-only market/account source used by the autonomous supervisor."""

    def read(self) -> AutonomousSnapshot:
        """Return one validated local observation or fail closed."""
        ...


class DecisionServicePort(Protocol):
    """Narrow decision boundary used by the supervisor."""

    def decide(self, command: DecisionCommand) -> DecisionOutcome:
        """Run the existing strategy/AI/risk/execution decision workflow."""
        ...


class ExecutionStatePort(Protocol):
    """Read-only durable execution state used to prevent parallel autonomous intents."""

    def status_counts(self) -> dict[str, int]:
        """Return execution-state counts."""
        ...


class ClockPort(Protocol):
    """UTC clock used for deterministic autonomous tests."""

    def now(self) -> datetime:
        """Return current aware UTC time."""
        ...


class AutonomousDemoSupervisor:
    """Generate at most one new DEMO execution intent while durable state is clear."""

    def __init__(
        self,
        *,
        service: DecisionServicePort,
        source: AutonomousSnapshotSource,
        execution_state: ExecutionStatePort,
        clock: ClockPort,
        node_id: str,
        allowed_symbols: frozenset[str],
        max_snapshot_age: timedelta,
    ) -> None:
        if not node_id:
            raise ValueError("node_id must not be empty")
        if not allowed_symbols:
            raise ValueError("allowed_symbols must not be empty")
        if max_snapshot_age <= timedelta(0):
            raise ValueError("max_snapshot_age must be positive")
        self._service = service
        self._source = source
        self._execution_state = execution_state
        self._clock = clock
        self._node_id = node_id
        self._allowed_symbols = allowed_symbols
        self._max_snapshot_age = max_snapshot_age
        self._last_processed_bar: dict[str, datetime] = {}

    def run_cycle(self) -> tuple[DecisionOutcome, ...]:
        """Evaluate each unseen bar until one DEMO intent is queued."""
        if self._has_blocking_execution_state():
            return ()

        snapshot = self._source.read()
        now = self._clock.now()
        self._validate_snapshot_time(snapshot, now)

        if snapshot.account.open_position_count > 0:
            return ()

        outcomes: list[DecisionOutcome] = []
        ordered = sorted(
            snapshot.markets,
            key=lambda observation: (observation.decision_bar_time, observation.market.symbol),
        )
        for observation in ordered:
            symbol = observation.market.symbol
            if symbol not in self._allowed_symbols:
                continue
            if self._last_processed_bar.get(symbol) == observation.decision_bar_time:
                continue

            # Mark before the external AI call. An ambiguous infrastructure failure must never
            # trigger an automatic retry of the same bar in this process.
            self._last_processed_bar[symbol] = observation.decision_bar_time
            outcome = self._service.decide(self._build_command(snapshot, observation, now))
            outcomes.append(outcome)
            if outcome.status is DecisionOutcomeStatus.DEMO_QUEUED:
                break
        return tuple(outcomes)

    def _has_blocking_execution_state(self) -> bool:
        counts = self._execution_state.status_counts()
        return any(
            count > 0 and status in _BLOCKING_EXECUTION_STATUSES for status, count in counts.items()
        )

    def _validate_snapshot_time(self, snapshot: AutonomousSnapshot, now: datetime) -> None:
        future_skew = snapshot.acquired_at - now
        if future_skew > timedelta(seconds=2):
            raise AutonomousSnapshotError("autonomous snapshot timestamp is in the future")
        if now - snapshot.acquired_at > self._max_snapshot_age:
            raise AutonomousSnapshotError("autonomous snapshot is stale")
        if snapshot.account.observed_at != snapshot.acquired_at:
            raise AutonomousSnapshotError("account observation does not match snapshot acquisition")

    def _build_command(
        self,
        snapshot: AutonomousSnapshot,
        observation: AutonomousMarketObservation,
        now: datetime,
    ) -> DecisionCommand:
        symbol = observation.market.symbol
        stable_key = f"{self._node_id}:{symbol}:{observation.decision_bar_time.isoformat()}"
        request_id = uuid5(_AUTONOMY_NAMESPACE, stable_key)
        nonce_digest = hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:48]
        return DecisionCommand(
            request_id=request_id,
            request_timestamp=now,
            nonce=f"auto_{nonce_digest}",
            schema_version="1.0",
            node_id=self._node_id,
            market=observation.market,
            account=snapshot.account,
            inverse_conversion_derivations=self._conversion_derivations(
                observation,
                snapshot.account.currency,
            ),
        )

    @staticmethod
    def _conversion_derivations(
        observation: AutonomousMarketObservation,
        account_currency: str,
    ) -> tuple[InverseConversionRateDerivation, ...]:
        if observation.quote_currency == account_currency:
            return ()
        symbol = observation.market.symbol
        expected_pair = observation.base_currency + observation.quote_currency
        if observation.base_currency != account_currency or symbol != expected_pair:
            return ()
        return (
            derive_inverse_conversion_rate(
                source_currency=observation.quote_currency,
                target_currency=account_currency,
                broker_quote=BrokerFxQuote(
                    source_symbol=symbol,
                    base_currency=observation.base_currency,
                    quote_currency=observation.quote_currency,
                    bid=observation.market.bid,
                    ask=observation.market.ask,
                    observed_at=observation.market.observed_at,
                ),
            ),
        )
