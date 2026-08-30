# Demo Deployment Runbook

Demo broker execution is **not implemented or authorized in 0.1.0**. This runbook is an approval
gate, not deployment instructions.

Before introducing `demo`: complete deterministic out-of-sample testing, broker contract metadata
and currency conversion, durable PostgreSQL idempotency/recovery, independent MQL5 validation,
broker-side SL/TP, spread/staleness/position limits, reconciliation, kill switch, fault injection,
Windows hardening, backups, incident drills, and actual MetaEditor compilation. Obtain explicit
financial-risk and operational approval for limits.

Use only a clearly identified demo account with no real funds. Verify configuration rejects `live`,
place a minimal controlled demo test only under an approved change, reconcile every broker response,
and stop on any discrepancy. Never reuse demo credentials or configuration for production.
