# ADR-0018: Broker Contract and Snapshot Fingerprints

- Status: Accepted
- Date: 2026-08-31

## Context

Bid/Ask and account-dependent tick observations change frequently. Treating every quote move as
contract drift creates noise; excluding dynamic evidence from all identity loses auditability.

## Decision

Compute two SHA-256 identities over canonical JSON. The full snapshot hash includes acquisition,
quotes, permissions, dynamic tick values, and calculation cases. The contract hash includes
broker/terminal/account calculation identity and symbol contract terms but excludes those dynamic
observations and acquisition time. Diff output applies the same classification.

## Alternatives Considered

- One all-fields hash: rejected because quote changes obscure material contract stability.
- One static-only hash: rejected because a captured observation still needs complete identity.
- Ignore terminal/account fields: rejected because wrong-terminal/account evidence is unsafe.

## Consequences

Quote-only snapshots share a contract hash but have different full hashes. Terminal builds and
contract fields can deliberately change the contract hash. Classifications require reviewed schema
evolution.

## Security Impact

Hashes reveal tampering only against a trusted expected value and are not signatures. Future archive
authenticity requires controlled storage or artifact signing.

## Testing Impact

Regression tests prove deterministic identity, quote-only stability of contract hashes, material
change sensitivity, canonical round trips, and deterministic diff bytes.
