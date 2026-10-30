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

## Decision conversion input

Schema 1.0 keeps the existing optional `conversion_rates` field. It also accepts an optional
`inverse_conversion_quotes` collection. Each item explicitly identifies requested source and target
currencies, source broker symbol, broker pair base and quote currencies, Bid, Ask, and observed-at
UTC time; all decimal values remain JSON strings.

The API accepts only an exact reverse pair and, for this risk boundary, derives `source -> target`
stop-loss exposure as `Decimal(1) / bid`. For JPY-to-USD from USDJPY, the reviewed FIBOGroup
loss-side calibration therefore uses USDJPY Bid. Positive/profit conversion is distinct and the MT5
evidence for that case corresponds to `1 / ask`; neither observation establishes a universal rule
for every JPY-to-USD conversion. The API retains method, Bid price side, quote facts, and final
directed rate. There is no symbol lookup, midpoint/last use, arbitrary rate reversal, or cross-rate
path. Invalid quotes reject at the schema/domain boundary; missing, stale, future, and duplicate
applicable rates reject in risk. All provenance participates in the request fingerprint.

## Intent schema 1.0

An intent includes `execution_id`, `intent_id`, `request_id`, `node_id`, `created_at`, `expires_at`,
symbol, side, market-only order type, volume, requested reference price, required SL/TP, maximum
spread, signal/risk identities, nonce, request/risk SHA-256 fingerprints, and strategy identity.
UUIDs and UTC timestamps are strings. Every financial wire value is a decimal string.

The example strategy derives its default SL distance from the reviewed specification as 100 ticks
and its reward-to-risk-2 TP as 200 ticks. This preserves a `0.00100` stop for EURUSD/GBPUSD and uses
`0.100` for USDJPY. The EA still calculates market `request.price` from Ask for BUY or Bid for SELL,
but validates broker stop/target triggers against Bid for BUY and Ask for SELL, both initially and
from the final pre-send tick.

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
