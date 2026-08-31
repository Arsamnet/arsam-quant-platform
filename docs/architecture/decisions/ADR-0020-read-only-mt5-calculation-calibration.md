# ADR-0020: Read-Only MT5 Calculation Calibration

- Status: Accepted
- Date: 2026-08-31

## Context

Platform FX P/L assumptions and MT5 double-based account-currency results require evidence beyond
static tick metadata. Full margin policy is not yet designed.

## Decision

Permit only MT5 hypothetical calculation functions in the metadata probe. Archive exact BUY/SELL/
volume/prices/result/error inputs for profit and margin. Compare supported same-currency FX profit
against exact Python contract-size math with fingerprinted Decimal absolute/relative tolerances.
Missing evidence warns; a successful out-of-tolerance result blocks. Cross-currency cases remain
explicitly uncomputed without a directed rate. Margin is archived but does not enter RiskEngine.

## Alternatives Considered

- Place tiny demo orders: rejected because this milestone forbids any execution.
- Assume tick-value formula is universally exact: rejected across broker/instrument/account modes.
- Add a margin engine now: rejected as unvalidated scope expansion.

## Consequences

The foundation can reconcile real captures later without claiming equivalence today. Cross-currency
and non-FX comparisons require future calibrated conversion/calculation logic.

## Security Impact

Calculation functions cannot create or mutate broker state; automated scans still ensure no trade API
is introduced beside them.

## Testing Impact

Synthetic exact, boundary, mismatch, failure, missing, BUY/SELL, and conversion-required cases are
deterministic. Real results must not be invented.
