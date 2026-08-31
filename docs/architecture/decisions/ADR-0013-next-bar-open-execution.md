# ADR-0013: Next-Bar-Open Execution

- Status: Accepted
- Date: 2026-08-31

## Context

Filling a signal at the same historical close used to create it grants an unknowable price and
introduces look-ahead bias.

## Decision

A strategy observes complete bar N at its close. An approved paper intent is queued and may fill
only at the next bar for that symbol, using its open quote: Ask for BUY and Bid for SELL, plus adverse
fixed slippage. A changed or missing spread policy, invalid post-gap stop/target, expired intent, or
missing conversion rejects the fill. A position filled at the open may encounter SL/TP during that
same bar; exits are resolved at the bar close before evaluating a new signal.

## Alternatives Considered

- Same-close fills were rejected as unknowable.
- Choosing a favorable intra-bar price was rejected as optimistic.
- Delaying exits until another bar was rejected because it ignores observable post-open range.

## Consequences

Gap risk is explicit in requested versus executed entry. The initial model supports market-style
next-open entry only; limit/partial fills and tick sequencing remain future work.

## Security Impact

The policy cannot route to a real broker and cannot transform missing execution facts into a fill.

## Testing Impact

Tests bind accepted signals and fills to different bar indices and verify BUY/SELL quote semantics.
