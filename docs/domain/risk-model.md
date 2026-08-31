# Risk Model

## Purpose

The risk engine is a deterministic approval gate between an advisory signal and an execution
intent. It is not a profitability model. A rejection is final for that decision and cannot be
overridden by strategy or AI output.

## Bootstrap assumptions

- Trading mode is paper only.
- Supported symbols and their reviewed static specifications are configured explicitly.
- `SymbolSpecification` holds the symbol currencies, contract size, tick size/value semantics,
  volume grid, price digits, and maximum spread in ticks without depending on MT5.
- Per-trade stop exposure starts with
  `abs(entry - stop) / tick_size * tick_value * volume` in the declared tick-value currency.
- When the tick-value currency differs from the account currency, the caller must provide one fresh,
  directed `CurrencyConversionRate`. Missing, duplicate, stale, or future conversion data rejects.
- The account risk budget is `balance * max_risk_fraction`.
- The effective daily-loss limit is
  `min(balance * max_daily_loss_fraction, optional_absolute_daily_loss_cap)`; reaching the boundary
  blocks new trades.
- Market and request age are evaluated against an injected aware UTC clock.
- Unavailable or invalid AI always blocks. A configured AI-required policy also blocks disabled or
  abstaining assessments. With AI explicitly disabled and optional, deterministic strategies may
  operate without AI; an unexpected AI outage is never treated as disabled.

All financial inputs and calculations use `Decimal`. Bootstrap defaults are deliberately
conservative engineering values, not production risk recommendations:

- `max_daily_loss_fraction = 0.02`
- `max_daily_loss_absolute_cap = 200` account-currency units
- `max_trade_risk_fraction = 0.01`
- `max_open_positions = 3`
- static EURUSD/GBPUSD limits of 50 ticks (`0.00050`) and USDJPY 50 ticks (`0.050`)

The tick values are reviewed paper fixtures, not broker-perfect P/L metadata. Risk sizing still
excludes commissions, slippage, swap, dynamic tick values, portfolio correlation, and broker-specific
calculation modes. The backtest ledger models deterministic commission/slippage separately; demo
execution still requires comparison against real MT5 symbol metadata and broker results.

## Fail-closed rule order

The engine evaluates all available deterministic rules to produce an auditable set of rejection
reasons. Missing required state is rejected before financial approval. Core checks cover trading
mode, an independent symbol allowlist, specification availability, stale data, symbol-aware spread,
signal direction, stop loss, symbol/global volume bounds, position count, account-relative daily
loss, AI policy, conversion availability, and per-trade risk. An absent spread policy or required
currency conversion fails closed.

The application rejects a symbol absent from the current node's specification provider before
strategy, AI, calendar, risk, or execution calls. The Risk Engine still performs its own symbol
allowlist/specification checks when invoked directly; the early check is not a substitute for the
downstream control.

An `ExecutionIntent` may be constructed only from an approved `RiskDecision` associated with the
same signal. Application orchestration enforces this boundary and tests prove rejected decisions do
not invoke the execution adapter.

## Change control

Changing a limit default or weakening a rule requires explicit product/risk approval, an ADR or ADR
amendment, property tests at the boundary, regression coverage, and documentation of operational
migration. Static metadata and account-currency calculations must be validated against broker demo
contract metadata and hand reconciliations before any broker execution is authorized.
