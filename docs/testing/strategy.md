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
- `tests/unit/backtesting`: clocks, dataset validation, fingerprints, fills, costs, portfolio, metrics,
  and chronological splits
- backtesting integration/regression: golden fixture, future invisibility, CLI, and byte reproducibility
- broker-validation unit: strict schema/Decimal/UTC normalization, immutable models, mode/bitmask
  decoding, grids, mapping, tolerance boundaries, fingerprints/diff, stale/tampered input,
  severities/readiness, and forbidden MQL5 API scanning
- broker-validation integration: offline import/validation/diff CLI success, canonical bytes,
  malformed input, trusted-hash failure, and blocking exit codes
- demo execution: locked startup identity, live rejection, SL/TP/volume/grid/spread/position gates,
  authenticated strict contracts, atomic outbox replay keys, crash/restart blocking, transition and
  reconciliation uncertainty, and result/intent fact matching
- MQL5 static safety: trade APIs remain forbidden outside the one explicitly reviewed guard and
  that guard contains exactly one `OrderSend` call

Overall branch coverage must be at least 85%. Risk/core financial logic targets at least 95% where
practical. Coverage is evidence, not the objective: boundary values, invalid state, stale/future
timestamps, missing stops, daily loss, maximum volume/positions, economic blackout, AI status, and
non-invocation after rejection are explicit assertions.

Hypothesis is used for financial properties such as volume limits and monotonic risk. Broker grids
also receive explicit below/min/step/misaligned/max/above boundary examples. Seeds and
fixtures remain reproducible; deterministic backtests record dataset/configuration identity and an
explicit null seed while no randomness is configured.

## Quality gate

Run Ruff format and lint, strict mypy, pytest with branch coverage, and pre-commit. CI additionally
runs dependency audit. Tests must not be skipped merely because an external service is unavailable;
external integration tests will be opt-in and separate when those adapters exist.

The synthetic MT5 fixture is labelled not FIBOGroup data and not broker calibrated. Core tests never
import the official MetaTrader5 package, open a network, require credentials, or skip because a
terminal is unavailable. The lexical probe scan removes comments/strings before searching known
forbidden executable tokens; its limits always require human review and an independent MetaEditor
compilation release gate. That gate was completed before the official 0.4.0 broker evidence pair was
acquired on 2026-09-06.

The separate 0.5.0 execution EA compile gate is not complete until the Windows operator provides
MetaEditor output showing `0 errors, 0 warnings`. Real broker tests are manual, DEMO-only, ordered
EURUSD then GBPUSD then conversion-gated USDJPY, and never run in CI.
