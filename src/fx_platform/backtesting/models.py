"""Immutable configurations, ledger records, run identity, and reports."""

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from fx_platform.backtesting.dataset import HistoricalDatasetMetadata
from fx_platform.backtesting.serialization import canonical_json, fingerprint
from fx_platform.domain.common import (
    TradeSide,
    require_finite_decimal,
    require_positive_decimal,
    require_utc,
)
from fx_platform.domain.market import CurrencyConversionRate, SymbolSpecification
from fx_platform.domain.risk import RiskLimits


class ExitReason(StrEnum):
    """Deterministic supported simulated exit causes."""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class PositionStatus(StrEnum):
    """The initial portfolio holds only currently open positions."""

    OPEN = "open"


class AuditEventType(StrEnum):
    """Stable event names in chronological backtest audit output."""

    NO_SIGNAL = "no_signal"
    RISK_REJECTED = "risk_rejected"
    INTENT_ACCEPTED = "intent_accepted"
    INTENT_REJECTED = "intent_rejected"
    ENTRY_FILLED = "entry_filled"
    POSITION_CLOSED = "position_closed"


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyConfiguration:
    """Explicit versioned strategy identity and canonical effective parameters."""

    strategy_id: str
    strategy_version: str
    parameter_snapshot_json: str
    parameter_hash: str

    @classmethod
    def create(
        cls,
        *,
        strategy_id: str,
        strategy_version: str,
        parameters: dict[str, object],
    ) -> "StrategyConfiguration":
        snapshot = canonical_json(parameters)
        return cls(
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            parameter_snapshot_json=snapshot,
            parameter_hash=fingerprint(parameters),
        )

    def __post_init__(self) -> None:
        if not self.strategy_id or not self.strategy_version:
            raise ValueError("strategy identity must not be empty")
        if canonical_json(json.loads(self.parameter_snapshot_json)) != self.parameter_snapshot_json:
            raise ValueError("strategy parameter snapshot must be canonical JSON")
        if fingerprint(json.loads(self.parameter_snapshot_json)) != self.parameter_hash:
            raise ValueError("strategy parameter hash does not match snapshot")

    @property
    def parameters(self) -> dict[str, Any]:
        """Return a detached JSON-compatible parameter snapshot."""
        value = json.loads(self.parameter_snapshot_json)
        if not isinstance(value, dict):
            raise ValueError("strategy parameters must be a JSON object")
        return value


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionConfiguration:
    """All materially relevant deterministic simulated-fill assumptions."""

    commission_per_lot_per_side: Decimal = Decimal("3.50")
    slippage_ticks: Decimal = Decimal(1)
    spread_handling: str = "fixed_bar_spread"
    fill_timing: str = "next_bar_open"
    intra_bar_policy: str = "adverse_first"

    def __post_init__(self) -> None:
        for field_name, value in (
            ("commission_per_lot_per_side", self.commission_per_lot_per_side),
            ("slippage_ticks", self.slippage_ticks),
        ):
            require_finite_decimal(value, field_name)
            if value < Decimal(0):
                raise ValueError(f"{field_name} must not be negative")
        if self.spread_handling != "fixed_bar_spread":
            raise ValueError("only fixed_bar_spread is supported")
        if self.fill_timing != "next_bar_open":
            raise ValueError("only next_bar_open execution is supported")
        if self.intra_bar_policy != "adverse_first":
            raise ValueError("only adverse_first intra-bar handling is supported")

    def canonical_snapshot(self) -> dict[str, object]:
        return {
            "commission_per_lot_per_side": self.commission_per_lot_per_side,
            "slippage_ticks": self.slippage_ticks,
            "spread_handling": self.spread_handling,
            "fill_timing": self.fill_timing,
            "intra_bar_policy": self.intra_bar_policy,
            "swap_model": "unsupported_zero",
        }

    @property
    def configuration_hash(self) -> str:
        return fingerprint(self.canonical_snapshot())


@dataclass(frozen=True, slots=True, kw_only=True)
class SimulatedPosition:
    """Reproducible open position created from a risk-approved paper intent."""

    position_id: UUID
    execution_id: UUID
    signal_id: UUID
    risk_decision_id: UUID
    symbol: str
    side: TradeSide
    volume: Decimal
    requested_entry_price: Decimal
    reference_entry_price: Decimal
    executed_entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal | None
    opened_at: datetime
    entry_spread_cost: Decimal
    entry_commission: Decimal
    entry_slippage_cost: Decimal
    status: PositionStatus = PositionStatus.OPEN

    def __post_init__(self) -> None:
        require_utc(self.opened_at, "opened_at")
        for field_name, value in (
            ("volume", self.volume),
            ("requested_entry_price", self.requested_entry_price),
            ("reference_entry_price", self.reference_entry_price),
            ("executed_entry_price", self.executed_entry_price),
            ("stop_loss", self.stop_loss),
        ):
            require_positive_decimal(value, field_name)
        if self.take_profit is not None:
            require_positive_decimal(self.take_profit, "take_profit")
        for field_name, value in (
            ("entry_spread_cost", self.entry_spread_cost),
            ("entry_commission", self.entry_commission),
            ("entry_slippage_cost", self.entry_slippage_cost),
        ):
            require_finite_decimal(value, field_name)
            if value < Decimal(0):
                raise ValueError(f"{field_name} must not be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeRecord:
    """Immutable closed-trade ledger entry with separated transaction costs."""

    trade_id: UUID
    position_id: UUID
    signal_id: UUID
    risk_decision_id: UUID
    execution_id: UUID
    symbol: str
    side: TradeSide
    volume: Decimal
    requested_entry_price: Decimal
    executed_entry_price: Decimal
    exit_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal | None
    opened_at: datetime
    closed_at: datetime
    exit_reason: ExitReason
    gross_pnl: Decimal
    spread_cost: Decimal
    commission: Decimal
    slippage_cost: Decimal
    swap_cost: Decimal
    net_pnl: Decimal

    def __post_init__(self) -> None:
        require_utc(self.opened_at, "opened_at")
        require_utc(self.closed_at, "closed_at")
        if self.closed_at < self.opened_at:
            raise ValueError("trade cannot close before it opens")
        for field_name, value in (
            ("volume", self.volume),
            ("requested_entry_price", self.requested_entry_price),
            ("executed_entry_price", self.executed_entry_price),
            ("exit_price", self.exit_price),
            ("stop_loss", self.stop_loss),
        ):
            require_positive_decimal(value, field_name)
        for field_name, value in (
            ("gross_pnl", self.gross_pnl),
            ("spread_cost", self.spread_cost),
            ("commission", self.commission),
            ("slippage_cost", self.slippage_cost),
            ("swap_cost", self.swap_cost),
            ("net_pnl", self.net_pnl),
        ):
            require_finite_decimal(value, field_name)
        if min(self.spread_cost, self.commission, self.slippage_cost, self.swap_cost) < Decimal(0):
            raise ValueError("trade costs must not be negative")
        expected_net = (
            self.gross_pnl
            - self.spread_cost
            - self.commission
            - self.slippage_cost
            - self.swap_cost
        )
        if self.net_pnl != expected_net:
            raise ValueError("net_pnl does not match gross P/L less explicit costs")

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_id": self.trade_id,
            "position_id": self.position_id,
            "signal_id": self.signal_id,
            "risk_decision_id": self.risk_decision_id,
            "execution_id": self.execution_id,
            "symbol": self.symbol,
            "side": self.side,
            "volume": self.volume,
            "requested_entry_price": self.requested_entry_price,
            "executed_entry_price": self.executed_entry_price,
            "exit_price": self.exit_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "opened_at": self.opened_at,
            "closed_at": self.closed_at,
            "exit_reason": self.exit_reason,
            "gross_pnl": self.gross_pnl,
            "spread_cost": self.spread_cost,
            "commission": self.commission,
            "slippage_cost": self.slippage_cost,
            "swap_cost": self.swap_cost,
            "net_pnl": self.net_pnl,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestAuditEvent:
    """One immutable trace event emitted in logical-time order."""

    sequence: int
    event_type: AuditEventType
    occurred_at: datetime
    bar_index: int
    signal_id: UUID | None = None
    risk_decision_id: UUID | None = None
    execution_id: UUID | None = None
    trade_id: UUID | None = None
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_utc(self.occurred_at, "occurred_at")
        if self.sequence < 0 or self.bar_index < 0:
            raise ValueError("audit sequence and bar index must not be negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "bar_index": self.bar_index,
            "signal_id": self.signal_id,
            "risk_decision_id": self.risk_decision_id,
            "execution_id": self.execution_id,
            "trade_id": self.trade_id,
            "reasons": self.reasons,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestReport:
    """Deterministic realized-balance metrics; no annualized ratios are implied."""

    initial_balance: Decimal
    final_balance: Decimal
    final_equity: Decimal
    net_pnl: Decimal
    return_fraction: Decimal
    return_percentage: Decimal
    trade_count: int
    winning_trade_count: int
    losing_trade_count: int
    win_rate: Decimal | None
    gross_profit: Decimal
    gross_loss: Decimal
    profit_factor: Decimal | None
    maximum_drawdown: Decimal
    average_trade: Decimal | None
    average_winner: Decimal | None
    average_loser: Decimal | None
    expectancy: Decimal | None
    payoff_ratio: Decimal | None
    transaction_costs: Decimal
    realized_pnl: Decimal
    open_position_count: int
    drawdown_basis: str = "realized_balance"

    def to_dict(self) -> dict[str, object]:
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestRunMetadata:
    """Complete deterministic run identity without administrative wall-clock fields."""

    run_id: UUID
    engine_version: str
    dataset: HistoricalDatasetMetadata
    strategy: StrategyConfiguration
    risk_configuration_json: str
    risk_configuration_hash: str
    execution_configuration_json: str
    execution_configuration_hash: str
    starting_balance: Decimal
    account_currency: str
    random_seed: int | None
    started_at: datetime
    ended_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "engine_version": self.engine_version,
            "dataset": self.dataset.canonical_identity(),
            "strategy": {
                "strategy_id": self.strategy.strategy_id,
                "strategy_version": self.strategy.strategy_version,
                "strategy_parameters": self.strategy.parameters,
                "strategy_parameter_hash": self.strategy.parameter_hash,
            },
            "risk_configuration": json.loads(self.risk_configuration_json),
            "risk_configuration_hash": self.risk_configuration_hash,
            "execution_configuration": json.loads(self.execution_configuration_json),
            "execution_configuration_hash": self.execution_configuration_hash,
            "starting_balance": self.starting_balance,
            "account_currency": self.account_currency,
            "random_seed": self.random_seed,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestResult:
    """Canonical reproducible run result and immutable evidence."""

    metadata: BacktestRunMetadata
    report: BacktestReport
    trades: tuple[TradeRecord, ...]
    open_positions: tuple[SimulatedPosition, ...]
    audit_events: tuple[BacktestAuditEvent, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "metadata": self.metadata.to_dict(),
            "report": self.report.to_dict(),
            "trades": tuple(trade.to_dict() for trade in self.trades),
            "open_positions": tuple(_position_dict(position) for position in self.open_positions),
            "audit_events": tuple(event.to_dict() for event in self.audit_events),
        }

    def to_json(self) -> str:
        """Return byte-stable logical JSON for storage and golden comparisons."""
        return canonical_json(self.to_dict())


def risk_configuration_snapshot(
    *,
    limits: RiskLimits,
    specifications: tuple[SymbolSpecification, ...],
    conversion_rates: tuple[CurrencyConversionRate, ...],
) -> dict[str, object]:
    """Capture every risk input material to deterministic approval or sizing."""
    return {
        "limits": {
            "allowed_symbols": limits.allowed_symbols,
            "max_volume": limits.max_volume,
            "max_open_positions": limits.max_open_positions,
            "max_daily_loss_fraction": limits.max_daily_loss_fraction,
            "max_daily_loss_absolute_cap": limits.max_daily_loss_absolute_cap,
            "max_trade_risk_fraction": limits.max_trade_risk_fraction,
            "max_market_age": limits.max_market_age,
            "max_account_age": limits.max_account_age,
            "max_signal_age": limits.max_signal_age,
            "max_conversion_age": limits.max_conversion_age,
            "max_future_skew": limits.max_future_skew,
            "ai_required": limits.ai_required,
            "economic_calendar_required": limits.economic_calendar_required,
            "event_blackout_before": limits.event_blackout_before,
            "event_blackout_after": limits.event_blackout_after,
        },
        "symbol_specifications": tuple(
            {
                "symbol": specification.symbol,
                "base_currency": specification.base_currency,
                "quote_currency": specification.quote_currency,
                "contract_size": specification.contract_size,
                "tick_size": specification.tick_size,
                "tick_value": specification.tick_value,
                "tick_value_currency": specification.tick_value_currency,
                "volume_min": specification.volume_min,
                "volume_max": specification.volume_max,
                "volume_step": specification.volume_step,
                "price_digits": specification.price_digits,
                "max_spread_ticks": specification.max_spread_ticks,
            }
            for specification in sorted(specifications, key=lambda item: item.symbol)
        ),
        "conversion_rates": tuple(
            {
                "source_currency": rate.source_currency,
                "target_currency": rate.target_currency,
                "rate": rate.rate,
                "observed_at": rate.observed_at,
            }
            for rate in sorted(
                conversion_rates,
                key=lambda item: (
                    item.source_currency,
                    item.target_currency,
                    item.observed_at,
                ),
            )
        ),
    }


def _position_dict(position: SimulatedPosition) -> dict[str, object]:
    return {
        "position_id": position.position_id,
        "execution_id": position.execution_id,
        "signal_id": position.signal_id,
        "risk_decision_id": position.risk_decision_id,
        "symbol": position.symbol,
        "side": position.side,
        "volume": position.volume,
        "requested_entry_price": position.requested_entry_price,
        "reference_entry_price": position.reference_entry_price,
        "executed_entry_price": position.executed_entry_price,
        "stop_loss": position.stop_loss,
        "take_profit": position.take_profit,
        "opened_at": position.opened_at,
        "entry_spread_cost": position.entry_spread_cost,
        "entry_commission": position.entry_commission,
        "entry_slippage_cost": position.entry_slippage_cost,
        "status": position.status,
    }
