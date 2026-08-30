# ADR-0010: Per-symbol spread policy in ticks

- Status: Accepted
- Date: 2026-08-30

## Context

One absolute price-distance limit has different meaning for instruments with different tick sizes.

## Decision

Store an optional maximum spread tick count on each `SymbolSpecification`; derive the exact price
limit as `tick_size * max_spread_ticks` with `Decimal`. A missing policy rejects. The retired global
`FX_MAX_SPREAD` setting causes startup failure.

## Alternatives Considered

A global absolute threshold was rejected as instrument-unsafe. A dynamic market-regime policy was
deferred because it adds complexity not justified in the paper bootstrap.

## Consequences

EURUSD, USDJPY, and future instruments can express comparable policies in their native tick grids.
Static values still require broker-metadata validation before demo execution.

## Security Impact

Unknown spread configuration is never interpreted as permission.

## Testing Impact

Tests cover exact per-symbol thresholds, threshold breaches, and missing-policy rejection.
