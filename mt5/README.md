# MetaTrader 5 Boundary

This directory contains no Expert Advisor order implementation. Version 0.4.0 remains paper-only.
`metadata_probe/ReadOnlyMetadataProbe.mq5` exports schema-1.0 contract metadata and read-only
`OrderCalcProfit`/`OrderCalcMargin` evidence from an already authenticated terminal. It does not
request or persist credentials and contains no broker mutation API. The macOS development host
cannot perform MetaEditor compilation; the exact probe was independently compiled on the Windows
validation node against FIBO Group MT5 build `6140` with `0 errors, 0 warnings` before the official
read-only evidence pair was acquired on 2026-09-06. That evidence creates no execution authority.

A future EA will poll/exchange the versioned localhost contract documented in
`docs/architecture/trading-node.md` and independently validate authentication, node/schema, allowed
symbol, volume/position/spread limits, required broker-side SL/TP, expiry, replay/idempotency, and
explicit demo authorization before `OrderSend`. It will capture and reconcile broker responses and
safely manage already-open positions during Python/AI outages.

The future EA must never contain OpenAI/news keys, database credentials, control-plane secrets,
broker passwords in source, or direct OpenAI connectivity. Read `mt5/AGENTS.md` before adding code.
