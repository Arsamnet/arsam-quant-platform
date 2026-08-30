# MT5 Agent Guide

Read `mt5/README.md`, `docs/architecture/trading-node.md`, and the root `AGENTS.md` before changes.

- MQL5 is the last execution guard; validate strictly before any future `OrderSend`.
- Current phase is paper-only. Do not add real or demo broker order placement yet.
- Never embed OpenAI/news keys, database credentials, broker secrets, or control-plane secrets.
- Enforce allowed symbols, maximum volume/positions/spread, required broker-side SL/TP, request age,
  nonce/request id uniqueness, and idempotent execution.
- Reject stale, duplicate, malformed, unauthenticated (when enabled), or unsafe intents.
- The EA must not connect directly to OpenAI or external news services.
- Do not claim MQL5 compilation unless MetaEditor actually compiled the code.
