# Risk Domain Agent Guide

Read `docs/domain/risk-model.md`, `docs/architecture/decisions/ADR-0003-fail-closed-risk.md`, and the
root `AGENTS.md` before modifying this subsystem.

- The risk engine has final application-side rejection authority. AI cannot override it.
- Any unavailable, stale, malformed, inconsistent, or unknown required state fails closed.
- Never construct an execution intent from a rejected risk decision.
- Use `Decimal` for prices, volume, balances, P/L, and risk calculations. Use aware UTC datetimes.
- Preserve or strengthen safety-rule behavior. A backwards-incompatible relaxation needs an ADR,
  explicit review, regression tests, and migration guidance.
- Add example-based and property-based tests for limits, boundary values, stale data, daily loss,
  missing stops, and adapter non-invocation after rejection.
- Target at least 95% meaningful coverage for risk and core financial logic.
