# ADR-0017: Canonical Broker Contract Snapshot

- Status: Accepted
- Date: 2026-08-31

## Context

MT5 enums, bitmasks, doubles, server-local time, and account-specific metadata cannot safely leak
into broker-independent risk types or be reconstructed later from logs.

## Decision

Normalize strict schema-1.0 JSON into immutable broker/account/terminal/symbol/calculation models.
Financial text converts directly to `Decimal`; aware timestamps normalize to UTC; raw server time
remains explicitly offset-unknown when necessary. Known capability bits become explicit sets and
unknown bits remain visible. Passwords and raw logins are excluded.

## Alternatives Considered

- Store arbitrary MT5 dictionaries: rejected as mutable, weakly typed, and difficult to audit.
- Map directly to `SymbolSpecification`: rejected because that type cannot preserve dynamic quotes,
  terminal/account context, asymmetric tick values, modes, or stop/freeze metadata.
- Lenient/repairing parser: rejected because malformed evidence must fail closed.

## Consequences

Schema evolution must be explicit. Canonical archives are portable but remain untrusted until their
identity/provenance is verified. Supported FX metadata can be mapped only through a separate guard.

## Security Impact

Exact fields, duplicate-key rejection, bounded UTF-8 input, finite decimals, explicit timezones, and
no credential fields reduce malicious/tampered snapshot risk.

## Testing Impact

Synthetic tests cover every normalization boundary, unknown modes/bits, malformed numbers/times,
round trips, and missing metadata without broker connectivity.
