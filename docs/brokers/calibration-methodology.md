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

## Real calibration evidence

The official FIBOGroup read-only calibration pair was completed on 2026-09-06. The intended
environment was a FIBOGroup MT5 demo account using USD account currency, retail hedging position
mode, and 1:100 leverage. The terminal identified itself as FIBO Group MT5 build `6140`, and the
probe compiled independently in Windows MetaEditor with `0 errors, 0 warnings`.

The first canonical snapshot was acquired at `2026-09-06T04:07:05Z` and contained EURUSD, GBPUSD,
and USDJPY:

```text
snapshot_fingerprint =
cf6ac34433a8395843dd09feafa2814ed35771ce11c0926b1d092773e5938cc9

contract_fingerprint =
b4d54d0eba373156d577706d9eee4809d19703d5fa6a5179b493f25a52625569
```

All three symbol validations returned `status=warning`, `readiness=ready`, `blocking=0`, and exit
code `0`. EURUSD and GBPUSD each reported one non-blocking `spread_consistency` warning. USDJPY
reported that warning plus non-blocking `tick_value`, `tick_value_profit`, and `tick_value_loss`
warnings. Spread consistency means that the reported spread points did not exactly match Ask minus
Bid in the same observation; the tick-value warnings mean that dynamic observations differed from
the static platform expectation, not that universal broker equivalence was established. Because
USDJPY profit currency is JPY while the configured account currency is USD, the validator preserves
an explicit conversion-required result and does not claim broker-equivalent USDJPY P/L.

A second snapshot acquired at `2026-09-06T04:09:47Z` produced:

```text
snapshot_fingerprint =
cf818411849ef4ad59a8f16c10898c5abb194119a23bcf566e6c74b035a31d09

contract_fingerprint =
b4d54d0eba373156d577706d9eee4809d19703d5fa6a5179b493f25a52625569
```

The repeated validation again returned `readiness=ready` and `blocking=0` for all three symbols.
`fx-broker-diff` reported:

```text
contract_changed=false
contract_changes=0
dynamic_changes=14
```

Each distinct raw export independently reproduced its corresponding canonical snapshot and trusted
snapshot fingerprint. The raw files did not compare equal, as expected for separate observations.

This is evidence that dynamic market observations changed while the captured broker contract
projection remained stable across these two observations; it is not proof of universal broker
equivalence.

Read-only `OrderCalcProfit` evidence for EURUSD and GBPUSD agreed with the platform calculation
within configured tolerance. USDJPY remains intentionally conversion-dependent rather than having
an invented cross/inverse conversion. The first snapshot's read-only `OrderCalcMargin` observations
were approximately `11.61` for EURUSD, `13.52` for GBPUSD, and `10.00` for USDJPY at volume `0.01`,
which appears consistent with leverage `1:100`. Version 0.4.0 still makes no full broker-equivalence
or RiskEngine claim for margin.

Raw and canonical broker snapshots and generated reports remain outside Git under the ignored
`var/broker-snapshots/` and `var/broker-reports/` paths. No broker account identifier, password, or
other credential is committed.

The post-calibration repository quality gate completed with `328 passed`, total coverage `97.06%`,
successful Ruff formatting/linting, successful strict mypy validation, and successful pre-commit
checks.

This calibration evidence authorizes no demo or live execution. XAUUSD, non-FX calculation modes,
full margin equivalence, and explicit directed USDJPY currency-conversion calibration remain outside
the claims of version 0.4.0.
