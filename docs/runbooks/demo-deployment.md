# Demo Deployment Runbook

Demo broker execution is **not implemented or authorized in 0.4.0**. This runbook is an approval
gate, not deployment instructions.

The 0.4.0 read-only metadata probe and offline validation reports are prerequisites for future
calibration evidence, not authorization. Real FIBOGroup metadata has not yet been captured or
validated, and the probe has not yet been compiled in MetaEditor.

Before introducing `demo`: complete deterministic out-of-sample testing, validate static symbol
metadata and currency-risk calculations against broker contract data, add durable PostgreSQL
idempotency/recovery, independent MQL5 validation,
broker-side SL/TP, spread/staleness/position limits, reconciliation, kill switch, fault injection,
Windows hardening, backups, incident drills, and actual MetaEditor compilation. Obtain explicit
financial-risk and operational approval for limits.

Use only a clearly identified demo account with no real funds. Verify configuration rejects `live`,
place a minimal controlled demo test only under an approved change, reconcile every broker response,
and stop on any discrepancy. Never reuse demo credentials or configuration for production.
