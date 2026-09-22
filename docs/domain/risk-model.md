# Risk Model

## Purpose

The risk engine is a deterministic approval gate between an advisory signal and an execution
intent. It is not a profitability model. A rejection is final for that decision and cannot be
overridden by strategy or AI output.

## Bootstrap assumptions

- Trading mode is paper, or explicitly configured guarded demo. Live always rejects.
- Supported symbols and their reviewed static specifications are configured explicitly.
- `SymbolSpecification` holds the symbol currencies, contract size, tick size/value semantics,
  volume grid, price digits, and maximum spread in ticks without depending on MT5.
- Per-trade stop exposure starts with
  `abs(entry - stop) / tick_size * tick_value * volume` in the declared tick-value currency.
- When the tick-value currency differs from the account currency, the caller must provide one fresh,
  directed `CurrencyConversionRate`. It may be supplied directly or derived at the API boundary
  from an explicit exact reverse broker-pair quote. Missing, duplicate, stale, or future conversion
  data rejects.
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

The demo composition overrides exposure to exactly `max_volume = 0.01`,
`max_open_positions = 1`, and requires both directional stop loss and take profit. The EA repeats
these constraints against current broker symbol/account state. USDJPY remains blocked without the
fresh directed conversion used by current risk semantics.

The only reviewed derivation is an explicit exact-pair inverse. The request supplies requested
source/target currencies, source symbol, pair base/quote currencies, Bid, Ask, and observed-at time.
Pair base must equal the requested target and pair quote must equal the requested source. For
`JPY -> USD` from `USDJPY`, `rate = Decimal(1) / ask` because obtaining USD with JPY buys USD at the
USDJPY Ask. The immutable result retains all quote facts, method `inverse_exact_pair`, side `ask`,
and the directed rate. The domain performs no lookup. It never uses Bid, midpoint, last price,
arbitrary reverse-rate inference, or a cross/multi-hop path.

## Fail-closed rule order

The engine evaluates all available deterministic rules to produce an auditable set of rejection
reasons. Missing required state is rejected before financial approval. Core checks cover trading
mode, an independent symbol allowlist, specification availability, stale data, symbol-aware spread,
signal direction, stop loss, symbol/global volume bounds, position count, account-relative daily
loss, AI policy, conversion availability, and per-trade risk. An absent spread policy or required
currency conversion fails closed.

Direct and derived rates enter the same directed-rate collection. More than one applicable source,
including one direct rate plus one exact-inverse derivation, is ambiguous and rejects rather than
being selected by priority. Quote age is evaluated by the unchanged conversion freshness and
future-skew limits.

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

Version 0.4.0 provides a separate offline read-only mapper for supported, fully validated FX broker
snapshots. It does not replace the runtime static provider automatically and does not weaken any
RiskEngine check. Mapping rejects unsupported calculation/trade modes, missing or non-positive
grids, asymmetric tick values, and incompatible currencies. Future composition of broker-derived
specifications requires a separately reviewed startup-readiness gate. Version 0.5.0 does not claim
universal margin equivalence: MT5 `OrderCalcMargin` and `OrderCheck` remain authoritative final
preflight checks.
