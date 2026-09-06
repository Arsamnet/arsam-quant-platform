# Demo Deployment Runbook

Demo broker execution is **not implemented or authorized in 0.4.0**. This runbook is an approval
gate, not deployment instructions.

The 0.4.0 read-only metadata probe has now been independently compiled in Windows MetaEditor and
real FIBOGroup demo metadata has been captured and validated offline for EURUSD, GBPUSD, and USDJPY.
Repeated snapshots retained the same contract fingerprint and produced no blocking validation
finding. This is calibration evidence only and does not authorize demo or live order execution.

Before introducing `demo`: complete deterministic out-of-sample testing, validate static symbol
metadata and currency-risk calculations against broker contract data, add durable PostgreSQL
idempotency/recovery, independent MQL5 execution validation, broker-side SL/TP,
spread/staleness/position limits, reconciliation, kill switch, fault injection, complete the
remaining Windows deployment hardening, backups, and incident drills, and retain/review the
completed MetaEditor and broker-calibration evidence. Obtain explicit financial-risk and operational
approval for limits.

Use only a clearly identified demo account with no real funds. Verify configuration rejects `live`,
place a minimal controlled demo test only under an approved change, reconcile every broker response,
and stop on any discrepancy. Never reuse demo credentials or configuration for production.
