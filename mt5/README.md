# MetaTrader 5 Boundary

This directory intentionally contains no Expert Advisor order implementation. Version 0.1.0 is
paper-only and no MQL5 compilation is claimed.

A future EA will poll/exchange the versioned localhost contract documented in
`docs/architecture/trading-node.md` and independently validate authentication, node/schema, allowed
symbol, volume/position/spread limits, required broker-side SL/TP, expiry, replay/idempotency, and
explicit demo authorization before `OrderSend`. It will capture and reconcile broker responses and
safely manage already-open positions during Python/AI outages.

The EA must never contain OpenAI/news keys, database credentials, control-plane secrets, broker
passwords in source, or direct OpenAI connectivity. Read `mt5/AGENTS.md` before adding code.
