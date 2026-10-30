# ADR-0022: Guarded localhost DEMO execution

- Status: Accepted
- Date: 2026-09-06

## Context

Version 0.5.0 must submit real broker orders only to the validated FIBOGroup DEMO environment while
keeping live execution impossible even after Python/configuration/request failure. Python cannot be
the final authority because the authoritative account and symbol state exists inside MT5.

## Decision

An approved `RiskDecision` is the only source of an immutable `ExecutionIntent`. In demo mode the
application atomically inserts that intent into a local SQLite outbox. The dedicated MQL5 EA polls
the loopback-only API, independently validates fixed broker/account identity and every execution
limit, journals the identity in `FILE_COMMON`, runs `OrderCalcMargin` and `OrderCheck`, and has the
repository's sole reviewed `OrderSend` call.

Both Python and the EA default to disabled. Python rejects `live` at startup. The EA always requires
`ACCOUNT_TRADE_MODE_DEMO`; there is no override. A dedicated magic number and short correlation
marker link outbox state to MT5 orders, deals, and positions. Claimed or ambiguous work is never
redelivered; it must first reconcile against the journal and broker history.

Loopback requests use a shared bearer token compared in constant time by Python. This minimal
mechanism is deliberately scoped to one host; it is not suitable for a network boundary.

## Alternatives Considered

- Python `MetaTrader5` as executor: rejected because account checks would not be immediately inside
  the final terminal boundary.
- In-memory queue: rejected because restart could duplicate an order.
- Redis/PostgreSQL deployment for this milestone: rejected to avoid unrelated infrastructure work;
  the narrow single-node SQLite outbox uses full synchronization and WAL.
- Automatic retry after submission uncertainty: rejected because it can duplicate exposure.

## Consequences

An uncertain claim can halt new demo execution until operator reconciliation. Availability is
sacrificed for duplicate prevention. SQLite is DEMO-only and does not replace the longer-term
PostgreSQL audit target. Windows host hardening remains deferred and the node is not production-ready.

## Security Impact

Live accounts fail independently in Python and MQL5. Local host compromise remains a material
residual risk because bearer-token localhost transport does not provide process identity or TLS.

## Testing Impact

CI proves startup barriers, risk limits, strict wire data, authentication, outbox uniqueness,
restart behavior, result transitions, unknown-state failure, and exactly one reviewed MQL5
execution boundary. MetaEditor compilation and controlled broker evidence remain manual gates.
