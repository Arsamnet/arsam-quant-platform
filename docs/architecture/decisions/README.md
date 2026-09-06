# Architecture Decision Records

Accepted decisions are append-only records. Supersede an ADR with a new ADR instead of rewriting
the original rationale. File names use `ADR-NNNN-short-title.md`.

- [ADR-0001: Python domain engine and MQL5 execution boundary](ADR-0001-python-mql5-boundary.md)
- [ADR-0002: AI is advisory only](ADR-0002-ai-advisory-only.md)
- [ADR-0003: Fail-closed risk architecture](ADR-0003-fail-closed-risk.md)
- [ADR-0004: Single-node MVP and future control plane](ADR-0004-single-node-future-control-plane.md)
- [ADR-0005: PostgreSQL persistence](ADR-0005-postgresql-persistence.md)
- [ADR-0006: Early symbol validation with risk defense in depth](ADR-0006-early-symbol-validation.md)
- [ADR-0007: Account-relative daily loss limits](ADR-0007-account-relative-daily-loss.md)
- [ADR-0008: Broker-independent symbol specifications](ADR-0008-symbol-specification.md)
- [ADR-0009: Explicit account-currency risk calculation](ADR-0009-account-currency-risk.md)
- [ADR-0010: Per-symbol spread policy in ticks](ADR-0010-per-symbol-spread-policy.md)
- [ADR-0011: Deterministic event-driven backtesting](ADR-0011-deterministic-event-backtesting.md)
- [ADR-0012: Historical monotonic clock](ADR-0012-historical-clock.md)
- [ADR-0013: Next-bar-open execution](ADR-0013-next-bar-open-execution.md)
- [ADR-0014: Explicit deterministic transaction costs](ADR-0014-explicit-transaction-costs.md)
- [ADR-0015: Adverse resolution of intra-bar ambiguity](ADR-0015-adverse-intrabar-ambiguity.md)
- [ADR-0016: Read-only MT5 metadata boundary](ADR-0016-read-only-mt5-metadata-boundary.md)
- [ADR-0017: Canonical broker contract snapshot](ADR-0017-canonical-broker-contract-snapshot.md)
- [ADR-0018: Broker contract and snapshot fingerprints](ADR-0018-broker-contract-and-snapshot-fingerprints.md)
- [ADR-0019: Blocking broker validation policy](ADR-0019-blocking-broker-validation-policy.md)
- [ADR-0020: Read-only MT5 calculation calibration](ADR-0020-read-only-mt5-calculation-calibration.md)
- [ADR-0021: Cross-platform MT5 validation](ADR-0021-cross-platform-mt5-validation.md)

## Template

```text
# ADR-NNNN: Title

- Status: Proposed | Accepted | Superseded
- Date: YYYY-MM-DD

## Context
## Decision
## Alternatives Considered
## Consequences
## Security Impact
## Testing Impact
```
