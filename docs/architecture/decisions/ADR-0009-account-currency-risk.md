# ADR-0009: Explicit account-currency risk calculation

- Status: Accepted
- Date: 2026-08-30

## Context

Tick-value exposure is not necessarily denominated in the account currency. Implicit pair formulas
are difficult to audit and fail for broader instrument types.

## Decision

Calculate stop exposure from explicit tick size, tick value, and lot volume. If the declared
tick-value currency differs from the account currency, require exactly one fresh directed
`CurrencyConversionRate`. Do not infer inverse or cross rates. Missing, ambiguous, stale, or future
rates reject.

## Alternatives Considered

Symbol-name formulas and automatic inversion were rejected as hidden assumptions. Broker calls from
the domain were rejected as nondeterministic infrastructure coupling.

## Consequences

EURUSD/USD and GBPUSD/USD need no conversion; USDJPY/USD requires JPY-to-USD input. Results remain
paper estimates until reconciled with broker metadata, calculation modes, commissions, and fills.

## Security Impact

Infrastructure uncertainty cannot become approval, and all conversion inputs are time-bounded.

## Testing Impact

Hand-verifiable pair examples and every conversion failure state have deterministic unit coverage.
