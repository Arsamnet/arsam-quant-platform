# Test Agent Guide

Read `docs/testing/strategy.md` and the root `AGENTS.md` before modifying tests.

- Tests are deterministic and make no external network calls.
- Mock or fake only external boundaries; verify behavior and invariants, not implementation details.
- Every fixed bug receives a regression test under `tests/regression` when appropriate.
- Financial/risk boundaries, invalid inputs, timezones, duplicates, stale data, and fail-closed paths
  are mandatory. Use Hypothesis where it materially increases confidence.
- A rejected decision must be proven not to reach execution.
- Do not weaken assertions or coverage thresholds to make a gate pass.
