# Trading Node and Versioned Local Contracts

## Runtime

FastAPI is restricted to `127.0.0.1`, `::1`, or `localhost`; the supported demo command and MT5 EA
use `127.0.0.1`. The default `paper` composition retains the in-memory fake executor. The explicit
`demo` composition uses the same strategy/advisory/risk service but swaps the executor for the
durable local SQLite outbox.

```text
decision request -> request/node/symbol checks -> strategy -> optional AI/calendar
                 -> RiskEngine -> approved immutable intent -> SQLite pending row
                 -> authenticated EA claim -> terminal-side guards -> broker
                 -> strict result -> orders/deals/positions reconciliation
```

There is no direct API-to-broker endpoint. Only an approved risk decision can construct an intent.
The active decision audit remains in-memory in this local composition, while the demo outbox has
durable unique execution/intent/request/nonce/fingerprint keys. Replaying after Python restart is
therefore suppressed by the outbox even when the process audit cache is empty.

## Decision request

`POST /v1/decision` keeps schema `1.0`. It requires request UUID, aware timestamp, 16+ character
nonce, matching node ID, strict market/account snapshots, and optional explicit directed conversion
rates. The optional `inverse_conversion_quotes` collection carries a complete broker Bid/Ask
snapshot and an explicit requested conversion; Python never looks up a symbol. Financial values are
JSON strings. Extra fields, naive/stale/future time, wrong nodes, reused identity, unknown symbols,
missing required state, and invalid decimals reject.

When `FX_HMAC_SECRET` is set, send `X-FX-Signature: sha256=<hex>` where the digest is HMAC-SHA256 of
the exact bytes. Missing/malformed signatures reject and Python uses constant-time comparison.

USDJPY still requires a fresh, explicit JPY-to-USD rate for the reviewed static tick-value
semantics. A caller may supply that directed rate or request the reviewed exact inverse derivation
from a complete USDJPY quote, using `1 / ask`. Automatic inversion, arbitrary reverse-rate
inference, and cross rates remain forbidden. Accepted quote provenance is included in the request
fingerprint.

## Demo execution API

The demo endpoints and schema are defined in
[the execution contract](../execution/demo-execution-contract.md). They exist only after settings
validate explicit demo enablement, exact identity/limits, a 32+ character secret, and loopback bind.
The EA sends that secret as `X-FX-Execution-Token`; it never appears in payloads or logs.

`GET /v1/demo-execution/next` changes `pending` to `claimed` in one immediate transaction. A claimed,
submitted, filled, partially-filled, unknown, or reconciliation-failed row causes `409` and blocks
new delivery. No lease expiry requeues broker work.

## Fixed execution policy

Python configuration locks FIBO company/server, USD, retail hedging, leverage 100, three symbols,
0.01 lot, one position, required SL/TP, TTL 5–15 seconds, node, and magic. The MQL5 guard repeats the
safety-critical values as non-overridable constants immediately before broker submission. Its
independent `EnableDemoExecution` input defaults false.

The bearer token is the smallest reviewable mechanism compatible with MQL5 and one-host loopback.
It does not authenticate operating-system process identity and is not acceptable beyond localhost.
Remote transport requires a separately reviewed mutually authenticated design.
