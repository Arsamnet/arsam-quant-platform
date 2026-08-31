# MetaTrader 5 Boundary

This directory contains no Expert Advisor order implementation. Version 0.4.0 remains paper-only.
`metadata_probe/ReadOnlyMetadataProbe.mq5` exports schema-1.0 contract metadata and read-only
`OrderCalcProfit`/`OrderCalcMargin` evidence from an already authenticated terminal. It does not
request or persist credentials and contains no broker mutation API. MetaEditor compilation has not
yet been validated from the current macOS development environment.

A future EA will poll/exchange the versioned localhost contract documented in
`docs/architecture/trading-node.md` and independently validate authentication, node/schema, allowed
symbol, volume/position/spread limits, required broker-side SL/TP, expiry, replay/idempotency, and
explicit demo authorization before `OrderSend`. It will capture and reconcile broker responses and
safely manage already-open positions during Python/AI outages.

The future EA must never contain OpenAI/news keys, database credentials, control-plane secrets,
broker passwords in source, or direct OpenAI connectivity. Read `mt5/AGENTS.md` before adding code.
