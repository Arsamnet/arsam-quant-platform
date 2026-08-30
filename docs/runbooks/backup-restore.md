# Backup and Restore Runbook

The bootstrap has no production database. Before durable deployment, define encrypted PostgreSQL
logical/physical backup schedules, retention, off-host copies, access roles, integrity checks, and
recovery point/time objectives. Include audit data, configuration versions, migration revision,
strategy packages, and operational documentation; exclude plaintext secrets from ordinary archives.

Restore into an isolated environment, verify checksums, apply the recorded migration sequence,
validate UTC/idempotency constraints and row counts, and run the complete quality and reconciliation
suite. Rotate secrets if exposure is possible. Do not enable new trades until restored audit,
account, position, and broker state agree. Record the drill outcome and corrective actions.
