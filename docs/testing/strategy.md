# Testing Strategy

## Principles

Tests validate observable safety behavior and domain invariants. Unit tests are deterministic,
inject time, and never use external networks, OpenAI, PostgreSQL, or MetaTrader. Fakes appear only
at external boundaries. A regression test accompanies each corrected safety defect.

## Suites

- `tests/unit`: value-object invariants, strategy behavior, risk rules, adapters, and configuration
- `tests/integration`: FastAPI plus the complete in-memory paper vertical slice
- `tests/contract`: versioned wire shape, exact decimal encoding, HMAC, and rejection semantics
- `tests/regression`: replay, duplicate, and previously observed safety failures

Overall branch coverage must be at least 85%. Risk/core financial logic targets at least 95% where
practical. Coverage is evidence, not the objective: boundary values, invalid state, stale/future
timestamps, missing stops, daily loss, maximum volume/positions, economic blackout, AI status, and
non-invocation after rejection are explicit assertions.

Hypothesis is used for financial properties such as volume limits and monotonic risk. Seeds and
fixtures remain reproducible; deterministic backtests will record their dataset and random seed.

## Quality gate

Run Ruff format and lint, strict mypy, pytest with branch coverage, and pre-commit. CI additionally
runs dependency audit. Tests must not be skipped merely because an external service is unavailable;
external integration tests will be opt-in and separate when those adapters exist.
