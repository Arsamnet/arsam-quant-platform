# Backtesting Methodology

Version 0.3.0 is a deterministic engineering simulator, not evidence of profitability or broker
equivalence. Given the same canonical dataset, strategy parameters, risk limits, symbol
specifications, conversion observations, execution assumptions, starting balance, account currency,
and engine version, it produces the same logical result and identifiers.

## Critical information boundary

> **NO FUTURE DATA MAY ENTER A STRATEGY DECISION.**

The engine consumes an immutable `HistoricalEventStream` in its supplied chronological order. It
does not give strategies a dataframe, dataset slice, iterator, cache, or precomputed future-aware
indicator. At a bar close the existing strategy interface receives only a `MarketSnapshot` containing
that close and the previous already-visible midpoint close. Point-in-time currency replay similarly
returns only the latest observation at or before logical time.

The first bar has no prior bar, so its `previous_close` is its own midpoint close. This creates an
explicit warm-up/no-signal event for the current example strategy without reading the second bar.

## Event order

For every bar, in dataset order:

1. Advance `BacktestClock` to bar open.
2. Fill risk-approved intents from earlier bars at the current open, or record a fill rejection.
3. Advance the clock to bar close, when the complete OHLC range becomes available.
4. Resolve exits for open positions, including positions filled at this bar open. A simultaneous
   SL/TP touch resolves to stop loss.
5. Mark remaining positions to executable close and update portfolio equity.
6. Build current market and account snapshots.
7. Evaluate the versioned strategy with only visible state.
8. Use the explicit null AI advisor and null economic calendar.
9. Run the existing fail-closed `RiskEngine` with the matching `SymbolSpecification` and visible
   directed conversion rate.
10. Queue an approved paper `ExecutionIntent` for the next bar; rejected decisions never reach the
    simulated broker.
11. Append immutable audit events with deterministic trace identifiers.

Thus exits occur before a new decision at the same close. A decision cannot fill on that close. A
prior decision can fill at the next open and exit within that bar because all post-open movement is
then known at its close.

## Scope and interpretation

The initial engine supports one symbol and one fixed timeframe per run, full fills, SL and optional
TP, fixed bar spread, fixed deterministic slippage, per-lot-per-side commission, and in-memory
portfolio accounting. It uses no randomness (`random_seed` is `null`), network, PostgreSQL, OpenAI,
MT5, or broker SDK.

Metrics are based on realized balance. `maximum_drawdown` is peak-to-trough **realized balance
drawdown**, not equity drawdown. `final_equity` separately marks open positions to deterministic
liquidation at the final close. Profit factor is `None` when gross loss is zero; the canonical JSON
therefore never emits non-standard Infinity. Gross profit/loss are positive buckets of closed-trade
net P/L. Sharpe and Sortino are deliberately absent because return intervals and annualization are
not yet defined.

Chronological in-sample, validation, and out-of-sample splits never shuffle or overlap. Version
0.3.0 performs no optimization, parameter search, walk-forward selection, Monte Carlo simulation,
or performance claim.

See [data-contract.md](data-contract.md), [execution-model.md](execution-model.md), and
[reproducibility.md](reproducibility.md).
