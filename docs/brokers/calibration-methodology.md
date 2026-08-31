# Broker Calculation Calibration Methodology

Calibration establishes evidence; it does not establish strategy profitability or permit trading.
The repository fixture is explicitly synthetic, not FIBOGroup data, and not broker calibrated.

## Profit cases

The read-only probe records deterministic BUY and SELL inputs: exact symbol, side, volume, open
price, close price, observation time, success/error code, and MT5 result. For supported FX when the
profit currency equals the configured account currency, Python compares:

```text
direction = +1 BUY, -1 SELL
platform P/L = direction * (close - open) * contract_size * volume
```

If profit and account currencies differ, the report records that an explicit point-in-time directed
conversion is required and does not invent an inverse, cross, or server rate. MT5 failure remains a
warning with its numeric error code; no result is fabricated. A successful comparison outside the
explicit tolerance is blocking.

Money closeness is true when either absolute difference is at most
`absolute_money_tolerance` or relative difference against the larger absolute magnitude is at most
`relative_money_tolerance`. Defaults are `0.01` account-currency units and `0.0001`. Spread
consistency uses `tick_size * price_tolerance_ticks`, default zero. Boundaries are inclusive and all
values use `Decimal`; tolerance configuration is fingerprinted with the report.

These cases do not prove generic tick-value identity. The platform captures terminal generic,
profit, and loss tick values separately and does not assume `tick_value == contract_size *
tick_size` for every instrument.

## Margin cases

`OrderCalcMargin` inputs/results are archived as read-only evidence. Version 0.4.0 has no full margin
risk engine, performs no broker-equivalence claim for margin, and does not modify the existing Risk
Engine based on those results. A later reviewed milestone must define and reconcile leverage,
calculation-mode, currency-conversion, hedge/netting, and portfolio-margin semantics before use.

## Real calibration gate

Broker calibration code is complete, but real FIBOGroup metadata has not yet been captured or
validated. Required later evidence includes an independently compiled probe, actual intended demo
account identity/mode, snapshots for EURUSD/GBPUSD/USDJPY, hand-reconciled BUY/SELL P/L cases,
margin observations, repeated quote-only snapshots, contract drift checks, archive integrity, and
operator sign-off. XAUUSD and non-FX calculation modes remain deferred.
