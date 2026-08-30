# ADR-0003: Fail-Closed Risk Architecture

- Status: Accepted
- Date: 2026-08-30

## Context

Automated trade workflows combine market data, strategy output, optional AI advice, account state,
and external infrastructure. Missing or inconsistent state can make an apparently valid decision
unsafe.

## Decision

Risk is a deterministic domain service with final application-side rejection authority. Required
state that is missing, invalid, stale, unavailable, or inconsistent rejects a new trade. Risk emits
an immutable decision with machine-readable reasons. The application creates an execution intent
only after explicit approval. MQL5 will independently repeat last-line safety validation.

## Alternatives Considered

- Best-effort approval during dependency outages: rejected because it converts uncertainty into
  financial exposure.
- Allow AI to override risk: rejected because AI output is non-deterministic and untrusted.
- Put all controls only in MQL5: rejected because application decisions also require auditable,
  testable policy and defense in depth.

## Consequences

Some opportunities will be missed during outages or stale-state conditions. Decisions are safer,
deterministic, explainable, and independently testable. Rule changes require compatibility review.

## Security Impact

Compromised advisory inputs cannot directly authorize an order. Duplicate, stale, and malformed
requests are rejected at multiple boundaries.

## Testing Impact

Critical rules require boundary and property-based tests. Tests must demonstrate that a rejected
decision never invokes execution and that unexpected errors never become approval.
