# Demo Execution Contract

## Authority and transport

`POST /v1/decision` remains the only entry to strategy and risk. A rejected decision cannot create
an intent. In `demo` mode approval returns `demo_queued`; it does not mean an order was sent.

The EA uses these authenticated loopback endpoints:

- `GET /v1/demo-execution/next`: atomically claims one fresh intent; `204` means none.
- `POST /v1/demo-execution/result`: records broker submission/rejection state.
- `POST /v1/demo-execution/reconcile`: records broker-history/position reconciliation.
- `GET /v1/demo-execution/status`: returns non-secret mode and durable state counts.

Send `X-FX-Execution-Token` with the environment-owned
`FX_DEMO_EXECUTION_SECRET`. Python compares it in constant time. Endpoints are registered only in
validated demo mode and the application refuses non-loopback binding.

## Intent schema 1.0

An intent includes `execution_id`, `intent_id`, `request_id`, `node_id`, `created_at`, `expires_at`,
symbol, side, market-only order type, volume, requested reference price, required SL/TP, maximum
spread, signal/risk identities, nonce, request/risk SHA-256 fingerprints, and strategy identity.
UUIDs and UTC timestamps are strings. Every financial wire value is a decimal string.

The IDs, nonce, and request fingerprint are independently unique in the SQLite outbox. The EA also
persists and rejects these identities. Unknown fields are rejected by Python result schemas.

## Result semantics

Results capture broker retcode/description, order/deal IDs, requested/filled volume, requested and
executed prices, SL/TP, submission/execution/report times, symbol, side, reason, and reconciliation
state. Fill/confirmation states require a positive filled volume, execution price, and broker order
or deal identifier; rejected state cannot claim a fill. `unknown` and `reconciliation_failed` are
failures and block further claims. Only `position_confirmed` together with
`reconciliation_status=confirmed` represents reconciled success.

No status permits automatic `OrderSend` retry. A safe pre-submission rejection requires a new
risk-reviewed decision; a post-submission ambiguity requires reconciliation first.
