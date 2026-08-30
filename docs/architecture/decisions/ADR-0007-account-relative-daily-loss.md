# ADR-0007: Account-relative daily loss limits

- Status: Accepted
- Date: 2026-08-30

## Context

One absolute loss amount represents materially different drawdown percentages across account sizes.

## Decision

The Risk Engine computes `balance * max_daily_loss_fraction` and, when configured, takes the minimum
of that amount and an absolute hard cap. A realized P/L equal to or below the negative effective
limit rejects. Bootstrap defaults are fraction `0.02` and cap `200`; they are safety fixtures, not
production recommendations.

## Alternatives Considered

An absolute-only limit was rejected as non-scaling. A fraction-only limit was not selected because
the simple optional cap provides an additional auditable ceiling.

## Consequences

Smaller accounts receive proportionally smaller limits while larger accounts remain bounded by the
cap. The old `FX_MAX_DAILY_LOSS` setting is retired and causes startup failure.

## Security Impact

Misconfigured legacy limits do not silently weaken policy; startup fails with migration guidance.

## Testing Impact

Exact-boundary, below/beyond-boundary, cap, and property-based scaling tests are required.
