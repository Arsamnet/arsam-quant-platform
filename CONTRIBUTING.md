# Contributing

Read `AGENTS.md`, `docs/index.md`, and the nearest subsystem `AGENTS.md` before changing code. Use a
short-lived branch or trunk-based change, Conventional Commit subjects (`feat:`, `fix:`, `test:`,
`docs:`, `security:`, and related types), and do not rewrite shared history.

Behavior changes require deterministic tests and matching documentation. Risk changes require the
risk model, fail-closed ADR, property/boundary tests, and explicit review for any relaxation. Never
add live trading, secrets, paid services, or real broker credentials without explicit authorization.

Before review, run `scripts/check.ps1` or the commands in README. Explain warnings, unvalidated
platform behavior, migration impact, security impact, and technical debt in the handoff. Do not
claim MQL5 compilation without an actual MetaEditor result.
