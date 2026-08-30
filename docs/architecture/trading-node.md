# Trading Node and v1 Contract

## Runtime

FastAPI listens only on `127.0.0.1` by default. One decision request carries already observed market
and account snapshots. The service checks durable audit availability, request/node/replay state,
then rejects an unconfigured symbol before strategy or any downstream provider. For a configured
symbol it loads broker-independent metadata, runs the deterministic strategy, obtains explicit
AI/calendar states, evaluates risk, persists an intent stage, invokes the paper adapter, and
persists completion. The Risk Engine repeats symbol validation as defense in depth.

The in-memory repository is the active bootstrap adapter. SQLAlchemy/PostgreSQL is scaffolded but is
not selected by the composition root until transactional/recovery behavior receives integration and
operational review.

## Request contract

`POST /v1/decision` accepts JSON schema `1.0` with:

```json
{
  "schema_version": "1.0",
  "request_id": "40000000-0000-4000-8000-000000000004",
  "timestamp": "2026-08-30T12:00:00Z",
  "nonce": "unique_nonce_1234567890",
  "node_id": "local-paper-node",
  "market": {
    "snapshot_id": "10000000-0000-4000-8000-000000000001",
    "symbol": "EURUSD",
    "observed_at": "2026-08-30T12:00:00Z",
    "bid": "1.1000",
    "ask": "1.1002",
    "previous_close": "1.0990"
  },
  "account": {
    "account_id": "paper-account",
    "observed_at": "2026-08-30T12:00:00Z",
    "balance": "10000.00",
    "equity": "10000.00",
    "daily_realized_pnl": "0.00",
    "open_position_count": 0,
    "currency": "USD"
  },
  "conversion_rates": []
}
```

Financial values are decimal strings. Extra fields, naive timestamps, stale/future requests,
unknown symbols, wrong nodes, reused IDs/nonces, missing state, and invalid shapes reject or produce
an explicit non-execution outcome. `account.currency` defaults to `USD` for compatibility, and
`conversion_rates` is optional when the symbol tick value is already in account currency. A required
rate is a directed object with `source_currency`, `target_currency`, decimal-string `rate`, and
`observed_at`; the risk engine does not infer inverses or cross rates. A response contains trace IDs
only when the corresponding stage exists.

When `FX_HMAC_SECRET` is set, send `X-FX-Signature: sha256=<hex>`, where `<hex>` is HMAC-SHA256 of
the exact raw request bytes. Missing, malformed, wrong, or payload-mismatched signatures reject;
the 32-byte digest is compared in constant time. Replay checks remain independent and still run for
validly signed requests. With an empty secret, unauthenticated operation is permitted only for the
loopback bootstrap. HMAC is not a substitute for TLS; communication beyond localhost requires a
separately reviewed authenticated TLS design. Public binding remains prohibited.

## Future MQL5 validator

The EA must independently enforce schema/authentication, allowed symbol, maximum volume/positions,
required broker-side SL/TP, spread, request expiry, request/nonce uniqueness, idempotency, and demo
authorization before any `OrderSend`. It must capture the broker response and reconcile state. No EA
may contain SaaS, OpenAI, news, database, or broker secrets in source code.
