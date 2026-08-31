# ADR-0015: Adverse Resolution of Intra-Bar Ambiguity

- Status: Accepted
- Date: 2026-08-31

## Context

OHLC data proves that price levels were reached but cannot reveal their intra-bar order. A bar can
touch both stop loss and take profit after entry.

## Decision

When both SL and TP are reachable in the same unresolved bar, the simulator selects stop loss. Long
triggers use Bid OHLC; short triggers use Ask OHLC derived from the bar's explicit fixed spread. Stop
gaps fill at the adverse open when it is beyond the stop. Take profit fills no better than its target.

## Alternatives Considered

- TP-first was rejected as systematically optimistic.
- Guessing an OHLC path was rejected because no tick sequence supports it.
- Rejecting the entire run was considered safe but less useful than a disclosed conservative result.

## Consequences

Results may understate strategies that would have hit TP first, but never silently select the
profitable outcome. Tick replay can supersede this uncertainty in a later model version.

## Security Impact

Ambiguous market data cannot be converted into favorable execution by default.

## Testing Impact

The committed fixture deliberately touches both levels and the golden ledger records `stop_loss`.
