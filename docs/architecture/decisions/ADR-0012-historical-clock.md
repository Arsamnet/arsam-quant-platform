# ADR-0012: Historical Monotonic Clock

- Status: Accepted
- Date: 2026-08-31

## Context

Wall-clock reads in timestamps, freshness rules, or report identity make historical simulations
non-reproducible.

## Decision

Keep the application `Clock` protocol and `SystemClock`, add an injected `FixedClock`, and use a
dedicated `BacktestClock` for simulation. The historical engine initializes it from dataset time and
advances it only to bar open or close instants. It accepts aware UTC values and rejects backward
movement. Administrative wall-clock timestamps are absent from canonical results.

## Alternatives Considered

- Monkeypatching `datetime.now` was rejected as incomplete and process-global.
- Treating row order as time without a clock was rejected because risk freshness needs an instant.

## Consequences

Domain timestamps and risk evaluation use logical UTC. Backtest logs may have administrative log
timestamps, but those never enter a run ID, trade, metric, or serialized result.

## Security Impact

Unexpected host-clock state cannot authorize a historical decision.

## Testing Impact

Tests reject naive/backward time and prove a run succeeds even when `SystemClock.now` raises.
