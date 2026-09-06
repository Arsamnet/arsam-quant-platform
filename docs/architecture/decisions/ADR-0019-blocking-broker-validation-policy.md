# ADR-0019: Blocking Broker Validation Policy

- Status: Accepted
- Date: 2026-08-31

## Context

Not every observed MT5 difference has equal safety impact. A boolean result cannot distinguish an
informational server-time limitation from a wrong contract size or stale snapshot.

## Decision

Emit ordered checks with PASS, INFO, WARNING, or BLOCKING severity and expected/observed evidence.
Missing/stale/future identity, wrong account environment/currency/position mode, disabled
permissions, unavailable symbol, unsupported calculation mode, incompatible currencies/grids/
contract/volume, invalid quote, absent required modes/policy, unknown capability bits, and material
calculation disagreement are blocking. Dynamic spread/tick changes and conservative broker/platform
differences are warning or informational as documented.

## Alternatives Considered

- Boolean equality across all fields: rejected as both overblocking dynamic facts and underexplaining
  material mismatches.
- Automatically calibrate platform policy from a snapshot: rejected because observation cannot
  authorize or silently weaken risk policy.
- Allow unknown modes: rejected under fail-closed execution readiness.

## Consequences

Warnings remain visible without necessarily failing CLI validation. Blocking reports exit nonzero.
Readiness is informational only and has no execution wiring.

## Security Impact

Infrastructure uncertainty cannot become future permission. An explicit as-of makes replay/staleness
visible and deterministic.

## Testing Impact

Every blocking class, warning aggregation, boundary grid, freshness, overall status, and deterministic
report output has offline coverage.
