# ADR-0004: Single-Node MVP with Future Control Plane

- Status: Accepted
- Date: 2026-08-30

## Context

The first objective is reproducible development/backtesting and eventual demo validation on one
Windows node. Premature multi-tenancy would add identity, isolation, billing, deployment, and
operational complexity before trading safety is proven.

## Decision

Version 0.x begins as one isolated node with explicit `node_id` and local broker boundary. Ports and
contracts preserve a future split where a control plane manages identity, entitlements,
configuration, strategy packages, telemetry, and updates across isolated nodes. Billing, licensing,
and multi-tenancy are not implemented now; broker passwords remain local.

## Alternatives Considered

- Shared multi-tenant execution service now: rejected due to blast radius and premature complexity.
- No node identity: rejected because replay/audit and later enrollment require a stable boundary.

## Consequences

The MVP remains small and operable while avoiding a redesign of core domain rules. Future control
plane protocols still require dedicated ADRs and threat modeling.

## Security Impact

Isolation limits account blast radius and avoids central broker-credential collection. Remote
configuration cannot later be allowed to silently weaken hard local limits.

## Testing Impact

Current tests verify node mismatch and replay rejection. Future tests must cover tenant/node
authorization, signed updates, offline behavior, and cross-node isolation.
