# ADR-0001: Python Domain Engine and MQL5 Execution Boundary

- Status: Accepted
- Date: 2026-08-30

## Context

Quantitative research, AI/data integration, and testable risk orchestration fit Python, while MT5 is
the broker-native environment and must protect the final execution boundary.

## Decision

Python owns normalized data, strategy, advisory orchestration, deterministic risk, audit, and intent
creation. A future MQL5 EA receives only a validated versioned localhost contract and independently
validates safety before broker-side SL/TP and execution. The bootstrap implements only a fake paper
adapter and no `OrderSend`.

## Alternatives Considered

- All logic in MQL5: rejected due to weaker research/data/AI ergonomics and test isolation.
- Python connects directly to the broker: rejected because it removes the broker-native last guard.
- Public remote execution API: rejected for the single-node threat model.

## Consequences

The contract and safety rules exist at two deliberate layers. Reconciliation and compatibility need
careful versioning, but broker faults cannot bypass the EA's independent checks.

## Security Impact

The API remains loopback-only and the EA contains no external-service or database secrets. Optional
HMAC protects local message integrity/replay defense in depth.

## Testing Impact

Python contract tests cover serialization and rejection. Future EA tests require actual MetaEditor
compilation and broker-demo fault/reconciliation tests; CI must not fake this result.
