# ADR-0005: PostgreSQL Persistence

- Status: Accepted
- Date: 2026-08-30

## Context

Decision, risk, execution, configuration, and future research metadata require durable relational
integrity, transactions, UTC timestamps, exact numerics, indexing, and operational backup tooling.

## Decision

PostgreSQL is the production database. SQLAlchemy 2.x provides the adapter, and Alembic owns all
schema changes. Domain/application layers depend only on repository protocols. Unit tests use memory
and SQLite adapter tests; PostgreSQL is not required for the core suite.

## Alternatives Considered

- SQLite production: rejected for the intended concurrent/service operations and PostgreSQL target.
- Unversioned/manual SQL: rejected because schema history and repeatable deployment are mandatory.
- Redis as primary persistence: rejected because it does not replace relational audit integrity.

## Consequences

Operators must manage migrations, roles, backups, and restore drills. The active bootstrap remains
in-memory until transaction/recovery composition is reviewed; Redis may be added only for a proven
need.

## Security Impact

PostgreSQL should bind locally, use least-privilege roles, encrypted backups, controlled credentials,
and uniqueness constraints for replay protection. Database uncertainty blocks required workflows.

## Testing Impact

Repository and migration behavior need integration tests. CI core tests remain service-independent;
future release gates add ephemeral PostgreSQL migration/rollback and recovery verification.
