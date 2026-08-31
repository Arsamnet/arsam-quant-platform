# Arsam Quant Platform

A production-oriented engineering foundation for a measurable, reproducible, risk-controlled,
AI-assisted FX platform. Version **0.3.0** adds deterministic event-driven historical simulation
while remaining paper-only: it contains no MT5 order code, broker connection, or live-trading path.

The example previous-close strategy is deliberately illustrative and makes no claim of profit or
statistical edge.

## Safety status

- Only `FX_TRADING_MODE=paper` starts; `demo` and `live` fail configuration validation.
- AI is disabled by default, advisory only, schema constrained, and cannot create an order.
- Risk rejection prevents construction and execution of an intent.
- The only executor is an in-memory paper fake with ID/nonce replay protection.
- The API binds to loopback and rejects non-loopback configuration.
- Financial inputs are decimal JSON strings and domain calculations use `Decimal`.
- Unknown symbols stop before strategy/advisory work; risk repeats symbol validation independently.
- Daily loss is account-relative with an optional hard cap; spread and tick risk are symbol-aware.
- Backtests stream validated UTC bars, use a monotonic historical clock, and expose no future bars.
- Next-bar Bid/Ask fills, spread, commission, slippage, SL/TP, and adverse ambiguity are explicit.
- Dataset, strategy, risk, execution, run, trade, and report identities are reproducible.

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
an explicit fresh directed conversion rate.

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

The platform validates architecture and simulation reproducibility, not trading performance or
broker accuracy. The recommended next increment is broker-contract calibration against captured MT5
demo metadata and hand-reconciled calculations. Demo execution remains out of scope until those
controls and an independently compiled EA are reviewed.
