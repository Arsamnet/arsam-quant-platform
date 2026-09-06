# MT5 Broker Contract Validation

Version 0.4.0 compares an imported snapshot with the reviewed paper `SymbolSpecification`. It does
not connect to MT5 and cannot submit or modify an order. An explicit UTC `--as-of` is required so
freshness and report bytes are reproducible rather than silently depending on wall time.

```text
uv run fx-broker-validate \
  --snapshot var/broker-snapshots/mt5.json \
  --symbol EURUSD \
  --as-of 2026-08-31T10:00:00Z \
  --expected-broker-company "Approved Broker Company" \
  --expected-broker-server "Approved-Demo-Server" \
  --output var/broker-reports/eurusd.json
```

Exit code `0` means no blocking finding, `2` means input/configuration failure, and `3` means at
least one blocking mismatch. A warning may still return zero. `readiness` is an informational
`ready`, `not_ready`, or `unknown` value and has no connection to trading-mode configuration or an
execution adapter.

## Severity policy

- `PASS`: observed value satisfies the explicit expectation.
- `INFO`: captured evidence or a disclosed limitation that is not itself a mismatch, such as an
  unknown server UTC offset or archived margin calculation.
- `WARNING`: dynamic or conservative differences that do not establish a broken contract, such as
  one wide spread, a changed tick-value observation, a lower broker minimum, or missing optional
  profit calibration evidence.
- `BLOCKING`: required evidence is missing, stale, in the future, malformed, unknown, or
  incompatible. Future execution readiness fails closed.

Blocking checks include a missing symbol, wrong account currency, non-demo account, wrong
hedging/netting mode, disconnected terminal, disabled account permissions, non-full symbol trade
mode, unsupported/unknown calculation mode, currency/contract/tick/digit/volume-step mismatch,
platform volumes outside broker bounds, invalid price/volume grids, missing market/filling mode,
unknown capability bits, invalid quote ordering, absent platform spread policy, or a read-only
profit-calculation disagreement beyond tolerance.

Expected broker company/server are pinned with CLI options for a passing readiness result. A
configured mismatch or omitted trusted expectation is blocking; captured identity alone cannot
authorize readiness. Terminal build is always captured and contract-fingerprinted.

The current supported calculation modes are MT5 Forex and Forex No Leverage. Futures, CFD, metal,
index, exchange, service-collateral, and unknown modes are preserved but blocking. In particular,
XAUUSD is not declared ready merely because a terminal exports it.

## Mapping to SymbolSpecification

`SymbolSpecificationMapper` remains outside the MT5-specific value type. It requires full symbol
trade mode, a supported FX calculation mode, positive point/tick/tick-value/contract/volume facts,
an ordered volume range, tick size aligned to point, quote currency equal to profit currency, and
exactly symmetric generic/profit/loss tick values. The current domain type has one tick value, so
asymmetric MT5 values cannot be represented and mapping fails closed. `max_spread_ticks` remains an
explicit platform risk policy and is supplied separately; it is not invented from one broker quote.

## Grids and freshness

Volume alignment is `(volume - volume_min) % volume_step == 0` inside inclusive min/max bounds.
Price alignment uses tick size, not point. `point == 10^-digits` and tick size must be an integer
multiple of point, but point need not equal tick size. Stop and freeze levels are captured in points
for a future final guard and do not change RiskEngine behavior in this release.

The default dynamic freshness window is five minutes with two seconds of future skew. Both the
snapshot acquisition time and the selected symbol observation time are checked. Contract
snapshots remain useful historical evidence after that window, but a stale snapshot is not evidence
of current readiness. Policy/tolerance values are included in `policy_fingerprint`; identical
snapshot, policy, explicit as-of, and software version yield byte-identical report JSON.

Use `fx-broker-diff --before ... --after ...` to separate contract changes from dynamic observations.
No diff or validation result enables demo or live execution.
