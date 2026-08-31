# Backtest Reproducibility

## Run identity

`BacktestRunMetadata` contains engine version, complete dataset identity/checksum, strategy ID and
version, canonical parameter snapshot/hash, complete risk configuration/hash, complete execution
configuration/hash, starting balance, account currency, random seed (`null` in 0.3.0), and logical
dataset start/end.

Risk identity includes all `RiskLimits`, used symbol specifications and spread policies, and every
provided point-in-time conversion observation. Execution identity includes commission, slippage,
fixed-spread handling, next-open timing, adverse-first ambiguity, and unsupported-zero swap. SHA-256
hashes operate on canonical JSON with normalized decimals and deterministic collection ordering.

The run UUID is UUIDv5-derived from those logical inputs. Market snapshot, signal, AI assessment,
risk decision, decision, execution, position, and trade UUIDs derive from the run and event index.
No system time, process ID, filesystem path, hash randomization, or random generator enters identity.

## Canonical result

`BacktestResult.to_json()` produces sorted, compact, standards-compliant JSON. Decimal values are
strings, UTC datetimes use `Z`, UUIDs/enums use stable strings, and undefined ratios use JSON `null`.
It contains metadata, report, immutable closed trades, remaining open positions, and ordered audit
events. Repeated runs with identical logical inputs are byte-equivalent.

Administrative structured log timestamps may differ and are intentionally outside canonical output.
INFO logs summarize a run; detailed trace IDs are emitted at DEBUG and preserved in result audit
events. Logs never contain datasets, account payloads, environment variables, or credentials.

## Local CLI

```text
uv run fx-backtest \
  --dataset tests/fixtures/backtesting/eurusd_sample.csv \
  --initial-balance 10000 \
  --output /tmp/backtest-report.json
```

Optional flags set dataset/source labels, account currency, commission, and slippage. Invalid data,
configuration, paths, missing symbol/conversion metadata, or accounting uncertainty exits non-zero.
The command performs no download, database access, AI call, MT5 connection, or broker action.

To reproduce a result, retain the exact code/engine version, CSV logical content, metadata labels,
strategy/configuration values, symbol specifications, conversion observations, starting balance, and
account currency. Broker equivalence cannot be inferred until a later calibration milestone.
