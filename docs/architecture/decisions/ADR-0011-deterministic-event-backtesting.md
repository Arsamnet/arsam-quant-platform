# ADR-0011: Deterministic Event-Driven Backtesting

- Status: Accepted
- Date: 2026-08-31

## Context

Research results must exercise the production-oriented strategy and risk behavior without a toy
parallel engine, network, database, AI provider, MT5, or broker. Passing a complete dataframe to a
strategy would also make future-data leakage difficult to prevent or audit.

## Decision

Implement a chronological event stream over immutable validated bars. The backtest composition
reuses `StrategyEvaluator`, the null AI/calendar paths, `RiskEngine`, `ExecutionIntent`, and
`SymbolSpecification`. A simulated broker and in-memory portfolio are outer-layer backtesting
components. Each strategy call receives only the current close snapshot, the prior visible close,
and the already-resolved matching specification; static reviewed contract facts are not future
market data.
Run, dataset, configuration, signal, risk, execution, position, and trade identities are derived
deterministically.

## Alternatives Considered

- A dataframe/vectorized toy engine was rejected because it duplicates rules and exposes future data.
- Reusing the immediate paper fake was rejected because it cannot model next-bar fills or SL/TP.
- Database-backed runs were deferred because reproducibility does not require persistence.

## Consequences

Version 0.3.0 prioritizes auditable bar simulation over throughput and supports one symbol per run.
No future bar or rate is available to a decision, and identical logical inputs produce identical JSON.

## Security Impact

The engine has no network, remote AI, database, MT5, broker SDK, credentials, or non-paper intent.

## Testing Impact

Regression tests cover future invisibility, wall-clock independence, domain-risk rejection,
transaction costs, deterministic IDs, and byte-identical results.
