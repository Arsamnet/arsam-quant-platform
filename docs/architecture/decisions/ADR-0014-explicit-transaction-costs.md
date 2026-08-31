# ADR-0014: Explicit Deterministic Transaction Costs

- Status: Accepted
- Date: 2026-08-31

## Context

Zero or hidden costs can materially overstate historical results, while broker-specific assumptions
have not yet been calibrated.

## Decision

Each bar carries a non-negative fixed Bid/Ask spread. Gross trade P/L uses midpoint reference prices;
spread cost is the two half-spreads, deterministic slippage is a configured adverse tick distance on
entry and exit, and commission is a configured account-currency amount per lot per side. Net P/L is
exactly gross P/L minus spread, commission, slippage, and swap. Swap is unsupported and explicitly
zero. All values use `Decimal`, and the complete execution configuration is fingerprinted.

## Alternatives Considered

- Zero implicit spread and commission were rejected as misleading.
- Hiding spread inside fills without a ledger field was rejected as unauditable.
- Random slippage was deferred; no seed or randomness is needed in this milestone.

## Consequences

The model is deterministic and calibratable but does not claim broker accuracy. Quote-currency P/L
requires a fresh directed account-currency conversion.

## Security Impact

Missing conversion or symbol metadata fails closed; no broker assumptions are invented.

## Testing Impact

Hand-reconciled tests cover each cost and prove positive costs cannot improve an unchanged trade path.
