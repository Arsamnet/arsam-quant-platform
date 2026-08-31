# Backtesting Agent Guide

- No future bar, conversion, or revised point-in-time value may enter a decision.
- Simulation time comes only from `BacktestClock`; never use wall time for logical results.
- Backtests make no network, broker, MT5, database, or external-AI calls.
- Use `Decimal` for all prices, money, costs, P/L, and metrics.
- Bid/Ask, commissions, and deterministic slippage remain explicit and fingerprinted.
- Dataset and configuration identity must be canonical and reproducible.
- Resolve ambiguous same-bar SL/TP touches conservatively with the adverse exit.
