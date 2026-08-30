# ADR-0006: Early symbol validation with risk defense in depth

- Status: Accepted
- Date: 2026-08-30

## Context

An unconfigured symbol could previously reach strategy and advisory boundaries before the Risk
Engine rejected it. That creates unnecessary work and allows irrelevant infrastructure failures to
obscure a deterministic rejection.

## Decision

After replay, node, and request-time checks, the application requires a symbol specification for
the current node before calling strategy, AI, calendar, risk, or execution. It returns
`unknown_symbol` without signal, risk, or execution identifiers when none exists. The Risk Engine
retains an independent allowlist and specification check for every direct evaluation.

## Alternatives Considered

Risk-only validation was rejected because it permits unnecessary upstream work. Removing the Risk
Engine check was rejected because it would turn one orchestration check into a single point of
failure.

## Consequences

Unknown symbols terminate earlier and create a smaller audit trace. Configuration must keep the
node provider and Risk Engine allowlist aligned; the composition root derives both from one setting.

## Security Impact

Untrusted symbols cannot trigger advisory or economic-provider calls, and downstream defense in
depth remains intact.

## Testing Impact

Tests prove non-invocation of strategy, AI, calendar, risk, and execution, plus direct Risk Engine
unknown-symbol rejection.
