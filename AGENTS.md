# Agent Guide

## Mission and phase

Build a measurable, reproducible, risk-controlled commercial FX platform. The current phase permits
paper and explicitly guarded FIBOGroup DEMO execution; there is no live broker execution.

## Mandatory invariants

- Trading decisions fail closed. Infrastructure uncertainty never becomes approval.
- AI is advisory only. Risk and execution safety controls can always reject.
- `paper` is the default; `demo` requires every v0.5.0 guard; `live` must fail startup.
- Financial values use `Decimal`; domain timestamps are timezone-aware and stored as UTC.
- Never commit or log secrets, credentials, authorization headers, or customer data.

## Boundaries and repository map

Dependencies point inward: `domain` <- `application` <- `adapters`/`api`.

- `src/fx_platform/domain`: framework-independent rules and value objects
- `src/fx_platform/application`: orchestration and boundary protocols
- `src/fx_platform/adapters`: external-system implementations
- `src/fx_platform/api`: local versioned HTTP contract
- `mt5`: read-only metadata probe plus the sole reviewed DEMO execution guard
- `tests`: deterministic unit, integration, contract, and regression suites
- `docs`: source of truth; begin at `docs/index.md`

Read the nearest nested `AGENTS.md` plus linked documentation before changing risk, MT5, or tests.

## Common commands

```text
uv sync --locked --all-extras
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
uv run pre-commit run --all-files
```

PowerShell equivalents live in `scripts/`.

## Change requirements

- Add behavioral tests for changed behavior; risk and financial edge cases require property tests
  where useful. Unit tests must not require external networks or PostgreSQL.
- Keep Ruff, mypy, pytest, coverage (>=85% overall; >=95% risk/core where practical), and
  pre-commit green. Never blanket-ignore failures.
- Update the matching docs and ADRs in the same change when behavior or architecture changes.
- Use Conventional Commits and Keep a Changelog. Do not rewrite history.

## Definition of done

The change preserves safety invariants, respects boundaries, has meaningful deterministic tests,
passes all applicable quality gates, contains no secrets, updates documentation, and reports any
validation that could not be performed.
