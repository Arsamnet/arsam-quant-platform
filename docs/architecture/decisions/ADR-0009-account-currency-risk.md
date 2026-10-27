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

## Amendment / v0.5.0 — 2026-10-27

Automatic or unbounded rate inversion remains forbidden, as does every multi-hop or cross-rate
derivation. Schema 1.0 now permits a caller to supply all facts for one exact reverse broker pair
and explicitly request a directed conversion. This is a narrow derivation boundary, not a market
data lookup and not permission to reverse an arbitrary `CurrencyConversionRate`.

The accepted relation is exact: broker pair base must equal the requested target currency and pair
quote must equal the requested source currency. The source symbol must match those pair currencies.
This milestone's derivation boundary is specifically for inverse conversion of stop-loss exposure
from the quote/profit currency into the account currency. The reviewed FIBOGroup loss-side
calibration for JPY-to-USD using USDJPY is `Decimal(1) / USDJPY bid`. Positive/profit conversion is
a different concept; the reviewed MT5 evidence for it corresponds to `1 / USDJPY ask`. Neither is a
universal rule that JPY-to-USD always uses one price side. Midpoint, last price, arbitrary
inversion, and cross rates are not accepted.

The immutable derivation retains requested currencies, source broker symbol, pair currencies, Bid,
Ask, observation time, `inverse_exact_pair` method, `bid` loss-side provenance, and final directed
rate. The caller supplies every fact; the domain performs no broker or network call. The
application passes only the resulting directed rates into `RiskEngine`, preserving the original
risk boundary.

Normal freshness and future-skew checks remain mandatory. Invalid identity, price, currency, or
timestamp data rejects at the input boundary. Missing, stale, future, or multiple applicable direct
and/or derived candidates reject in risk. Quote provenance participates in deterministic request
fingerprints. These constraints amend the prohibition only for this reviewed exact-pair operation;
all other inversion remains forbidden.
