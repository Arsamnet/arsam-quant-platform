# Incident Response Runbook

1. **Detect and classify:** record UTC time, affected node/version/account, symptoms, and whether
   positions exist. Do not copy secrets into the ticket.
2. **Contain:** prevent new trade decisions, preserve safe management of open positions, isolate
   compromised network paths, revoke suspected API/HMAC keys, and restrict administrator access.
3. **Preserve evidence:** protect structured logs, Windows events, MT5 journals, audit/database
   snapshots, process/network state, configuration/version hashes, and time synchronization data.
4. **Eradicate:** patch the verified cause, rotate credentials, rebuild compromised hosts from a
   trusted baseline, and review dependency/update integrity.
5. **Recover:** restore in an isolated environment, reconcile account/positions/audit with the
   broker, run regression/fault tests, obtain operational approval, and re-enable only paper/demo
   mode authorized for that release.
6. **Learn:** write a blameless timeline, root cause, impact, detection gaps, owner/due dates, and
   regression tests/runbook changes.

For uncertain state, stop new trading. Never assume an unavailable risk database, AI, calendar, or
broker response means approval. Escalate suspected real-money exposure immediately through the
organization's financial and security incident channels.
