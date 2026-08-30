# ADR-0008: Broker-independent symbol specifications

- Status: Accepted
- Date: 2026-08-30

## Context

A single global contract size cannot describe all FX pairs, metals, CFDs, or future broker symbols.
Domain risk rules must not depend on MT5 types or connectivity.

## Decision

Introduce immutable `SymbolSpecification` with currencies, contract size, tick size/value semantics,
volume grid, price digits, and optional maximum spread ticks. A provider protocol supplies the model.
Version 0.2.0 uses reviewed static paper fixtures for EURUSD, GBPUSD, and USDJPY.

## Alternatives Considered

Embedding MT5 dictionaries in risk code was rejected as an infrastructure dependency. Continuing
global constants was rejected because it is not instrument-safe.

## Consequences

A future MT5 metadata adapter can populate the same model after validation. Unsupported configured
symbols fail startup; missing runtime metadata fails risk evaluation.

## Security Impact

No broker connection or credential is introduced, and absent specifications cannot authorize trade.

## Testing Impact

Value-object invariants, startup rejection, volume grids, and missing-specification paths are tested.
