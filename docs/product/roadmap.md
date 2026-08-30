# Roadmap

1. **0.1 bootstrap (current):** paper-only vertical slice, safety boundaries, tests, docs, CI.
2. **Deterministic backtest:** event-driven engine, point-in-time data fixture, Bid/Ask spread,
   commission/slippage assumptions, reproducible snapshot/version/seed, and out-of-sample split.
3. **Broker contract hardening:** symbol contract metadata, currency conversion, position state,
   signed localhost intent polling, reviewed MQL5 validator, and real MetaEditor compilation.
4. **Demo validation:** explicit demo mode only after operational approval, fault injection,
   reconciliation, and kill-switch runbooks. Live remains disabled.
5. **Research expansion:** economic calendar fixture/provider, news classification isolation,
   walk-forward/Monte Carlo evaluation, and versioned AI assessment datasets.
6. **Commercialization:** separately reviewed control plane, node identity, entitlements, secure
   updates, telemetry, tenant isolation, and billing. Broker passwords stay on trading nodes.

Each stage needs its own acceptance criteria and must not pre-authorize the next stage.
