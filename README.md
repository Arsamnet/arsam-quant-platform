# Arsam Quant Platform

A production-oriented engineering foundation for a measurable, reproducible, risk-controlled,
AI-assisted FX platform. Version **0.5.0** adds guarded real execution against one exact FIBOGroup
DEMO environment. It is disabled by default, limited to 0.01 lot and one position, and is not
production-ready. Live trading remains impossible.

The example previous-close strategy is deliberately illustrative and makes no claim of profit or
statistical edge.

## Safety status

- `paper` remains the safe default. `demo` starts only with explicit enablement, locked identity,
  and an environment-owned secret. `live` always fails startup.
- AI is disabled by default, advisory only, schema constrained, and cannot create an order.
- Risk rejection prevents construction and execution of an intent.
- Paper uses the in-memory fake. Demo approvals enter a synchronized local SQLite outbox; the API
  never calls MT5 directly.
- The API binds to loopback and rejects non-loopback configuration.
- Financial inputs are decimal JSON strings and domain calculations use `Decimal`.
- Unknown symbols stop before strategy/advisory work; risk repeats symbol validation independently.
- Daily loss is account-relative with an optional hard cap; spread and tick risk are symbol-aware.
- Backtests stream validated UTC bars, use a monotonic historical clock, and expose no future bars.
- Next-bar Bid/Ask fills, spread, commission, slippage, SL/TP, and adverse ambiguity are explicit.
- Dataset, strategy, risk, execution, run, trade, and report identities are reproducible.
- Read-only MT5 exports normalize to immutable Decimal/UTC broker snapshots with separate full and
  contract SHA-256 fingerprints.
- Broker validation remains read-only and cannot enable execution.
- The MQL5 metadata probe is automatically scanned for forbidden trade APIs and was independently
  compiled in Windows MetaEditor with `0 errors, 0 warnings` before real read-only FIBOGroup capture.
- A separate default-off MQL5 EA is the sole reviewed `OrderSend` boundary and rechecks DEMO mode,
  broker/account identity, exposure, SL/TP, spread, margin, replay, and positions inside MT5.

See [ARCHITECTURE.md](ARCHITECTURE.md), [SECURITY.md](SECURITY.md), and
[docs/index.md](docs/index.md) before extending the system.

## Supported environment

- Python 3.12, 3.13, or 3.14 (CI covers 3.12/Linux and 3.14/Windows)
- Windows Server 2025 is the intended trading-node target
- uv 0.12.7 for locked dependency and environment management
- PostgreSQL is the production persistence target; unit tests need no database service

Docker Desktop is not a production requirement.

## Exact setup

PowerShell:

```powershell
git clone <repository-url> arsam-quant-platform
Set-Location arsam-quant-platform
./scripts/bootstrap.ps1
Copy-Item .env.example .env
./scripts/run-api.ps1
```

macOS/Linux:

```sh
git clone <repository-url> arsam-quant-platform
cd arsam-quant-platform
./scripts/bootstrap.sh
cp .env.example .env
./scripts/run-api.sh
```

The default `.env.example` is safe but its PostgreSQL password is only a placeholder. The current
in-memory API does not connect to PostgreSQL at startup. Never commit `.env`.

Check health at `http://127.0.0.1:8000/health`. OpenAPI is local at
`http://127.0.0.1:8000/docs`.

`POST /v1/decision` requires schema version `1.0`, UUIDs, a 16+ character nonce, matching configured
node ID, and request/market/account timestamps no more than 30 seconds old. All prices, balances,
P/L, and volumes on the wire are strings such as `"1.1002"`, never JSON numbers. The detailed
contract and HMAC procedure are in [trading-node.md](docs/architecture/trading-node.md). Accounts
default to USD for v1 compatibility; symbols whose tick value is not in the account currency require
an explicit fresh directed conversion rate. Schema 1.0 also accepts a complete exact reverse-pair
Bid/Ask snapshot in `inverse_conversion_quotes`; for inverse conversion of stop-loss exposure from
JPY to USD using USDJPY it derives the loss-side rate `1 / bid`, retains provenance in request
identity, and never infers a cross rate. Positive/profit conversion is a separate concept for which
the reviewed MT5 evidence corresponds to `1 / ask`.

## Guarded Windows DEMO validation

Do not attempt this on macOS/Linux or a live account. On the intended Windows node, configure the
explicit demo variables in `.env`, then run:

```powershell
./scripts/deploy-demo-node.ps1 -Mt5DataPath "<terminal-data-path>" -InstallEA
./scripts/start-demo-node.ps1
./scripts/check-demo-node.ps1
```

Compile `ArsamDemoExecutionGuard.mq5` in MetaEditor and require `0 errors / 0 warnings`. Add
`http://127.0.0.1:8000` to MT5 WebRequest allowlisting, attach the EA with
`EnableDemoExecution=false`, complete every negative gate, then explicitly arm it only for an
approved controlled test. See the
[demo deployment runbook](docs/runbooks/demo-deployment.md) and
[execution contract](docs/execution/demo-execution-contract.md).

## Deterministic backtest

Run the committed synthetic EURUSD fixture locally:

```text
uv run fx-backtest \
  --dataset tests/fixtures/backtesting/eurusd_sample.csv \
  --initial-balance 10000 \
  --output /tmp/backtest-report.json
```

The command validates the strict CSV contract, runs the existing strategy and fail-closed Risk
Engine with null AI/calendar adapters, prints a concise summary, and optionally writes canonical
JSON. It performs no network, database, MT5, broker, or external-AI operation. See the
[backtesting methodology](docs/backtesting/methodology.md),
[data contract](docs/backtesting/data-contract.md),
[execution model](docs/backtesting/execution-model.md), and
[reproducibility contract](docs/backtesting/reproducibility.md).

## Offline MT5 broker validation

Import the clearly synthetic fixture without MT5, Windows, credentials, or network access:

```text
uv run fx-mt5-import \
  --input tests/fixtures/broker_validation/synthetic_eurusd_valid.json \
  --output /tmp/mt5-snapshot.json

uv run fx-broker-validate \
  --snapshot /tmp/mt5-snapshot.json \
  --symbol EURUSD \
  --as-of 2026-08-31T10:00:00Z \
  --expected-broker-company "SYNTHETIC TEST BROKER - NOT FIBOGROUP DATA" \
  --expected-broker-server "SYNTHETIC-DEMO - NOT BROKER CALIBRATED" \
  --output /tmp/mt5-validation.json
```

Validation requires an explicit aware `--as-of`; malformed input or a blocking mismatch returns
nonzero. `fx-broker-diff` classifies contract changes separately from quotes and other observations.
Actual account snapshots are ignored under `var/broker-snapshots/` and must never be committed.
See the [metadata contract](docs/brokers/mt5-metadata-contract.md),
[validation policy](docs/brokers/mt5-validation.md),
[probe guide](docs/brokers/mt5-read-only-probe.md), and
[calibration methodology](docs/brokers/calibration-methodology.md).

## Quality commands

```text
uv sync --locked --all-extras
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
uv run pre-commit run --all-files
uv run pip-audit --skip-editable
```

On Windows, `./scripts/check.ps1` runs the first five checks. Overall branch coverage must remain at
least 85%; risk/core logic targets at least 95% where practical.

## Database migrations

Set `FX_DATABASE_URL` to a locally bound PostgreSQL database, then run:

```text
uv run alembic upgrade head
```

Do not manually mutate production schemas. The active local vertical slice intentionally uses the
in-memory audit repository; switching runtime persistence requires a reviewed composition change.

## Project status and next work

The implementation is ready for continued controlled Windows engineering validation, not release.
EURUSD completed the full 0.01 DEMO execution/reconciliation/replay/kill/restart validation. GBPUSD
then completed the required follow-up execution/protection/reconciliation gate; it did not repeat
the full replay/restart/kill-switch suite. The closed trades' net results are execution evidence
only, not strategy-performance evidence. A USDJPY request without conversion correctly failed with
`conversion_rate_unavailable`. Reviewed inverse-quote implementation/negative tests and local
quality gates are complete. Windows deployment and one controlled USDJPY 0.01 DEMO
execution/reconciliation remain required before considering the final v0.5.0 merge/tag. Windows
infrastructure hardening remains deferred.
