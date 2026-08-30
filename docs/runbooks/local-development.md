# Local Development Runbook

1. Install Git, supported Python 3.12-3.14, and uv 0.12.7.
2. Run `scripts/bootstrap.ps1` on Windows or `scripts/bootstrap.sh` elsewhere.
3. Copy `.env.example` to untracked `.env`; keep mode `paper` and host `127.0.0.1`.
4. Run `scripts/check.ps1`/`scripts/check.sh`.
5. Start with `scripts/run-api.ps1`/`scripts/run-api.sh`; verify `/health` reports paper/disabled.

Unit tests need no network or PostgreSQL. For migration work, create a local least-privilege
PostgreSQL database, replace the placeholder URL only in `.env`, and run `uv run alembic upgrade
head`. Never paste `.env`, tokens, account details, or complete request headers into issues/logs.

Clear build/test caches only when diagnosing tooling; they are ignored and not source. Do not delete
databases or migration history as a routine reset.
