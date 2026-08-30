# Risk Model

## Purpose

The risk engine is a deterministic approval gate between an advisory signal and an execution
intent. It is not a profitability model. A rejection is final for that decision and cannot be
overridden by strategy or AI output.

## Bootstrap assumptions

- Trading mode is paper only.
- Supported symbols are configured explicitly.
- One standard FX lot represents 100,000 base-currency units for the initial illustrative risk
  calculation. Broker-specific contract metadata will replace this assumption before demo trading.
- Per-trade monetary risk is `abs(entry_price - stop_loss) * volume * contract_size`.
- The account risk budget is `balance * max_risk_fraction`.
- `daily_realized_pnl <= -max_daily_loss` blocks new trades.
- Market and request age are evaluated against an injected aware UTC clock.
- Unavailable or invalid AI always blocks. A configured AI-required policy also blocks disabled or
  abstaining assessments. With AI explicitly disabled and optional, deterministic strategies may
  operate without AI; an unexpected AI outage is never treated as disabled.

These calculations use `Decimal`. They deliberately exclude currency conversion, pip-value
variation, commissions, slippage, and portfolio correlation. Those omissions are safe only for the
paper bootstrap because configured limits remain conservative and no broker order is possible.

## Fail-closed rule order

The engine evaluates all available deterministic rules to produce an auditable set of rejection
reasons. Missing required state is rejected before financial approval. Core checks cover trading
mode, known symbol, stale data, spread, signal direction, stop loss, volume, position count, daily
loss, AI policy, and per-trade risk.

An `ExecutionIntent` may be constructed only from an approved `RiskDecision` associated with the
same signal. Application orchestration enforces this boundary and tests prove rejected decisions do
not invoke the execution adapter.

## Change control

Changing a limit default or weakening a rule requires explicit product/risk approval, an ADR or ADR
amendment, property tests at the boundary, regression coverage, and documentation of operational
migration. Broker metadata and account-currency conversion must be implemented before broker demo
execution.
