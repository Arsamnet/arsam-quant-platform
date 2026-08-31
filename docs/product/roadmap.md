# Roadmap

1. **0.1 bootstrap (complete):** paper-only vertical slice, safety boundaries, tests, docs, CI.
2. **0.2 risk hardening (complete):** early symbol rejection, broker-independent static metadata,
   account-relative daily loss, explicit currency conversion, per-symbol spread, and HMAC review.
3. **0.3 deterministic backtest (complete):** event-driven engine, point-in-time data fixture,
   Bid/Ask spread,
   commission/slippage assumptions, reproducible snapshot/version/seed, and out-of-sample split.
4. **Recommended next—broker contract validation:** verify symbol metadata and currency risk against
   MT5 demo data,
   add position state,
   signed localhost intent polling, reviewed MQL5 validator, and real MetaEditor compilation.
5. **Demo validation:** explicit demo mode only after operational approval, fault injection,
   reconciliation, and kill-switch runbooks. Live remains disabled.
6. **Research expansion:** economic calendar fixture/provider, news classification isolation,
   walk-forward/Monte Carlo evaluation, and versioned AI assessment datasets.
7. **Commercialization:** separately reviewed control plane, node identity, entitlements, secure
   updates, telemetry, tenant isolation, and billing. Broker passwords stay on trading nodes.

Each stage needs its own acceptance criteria and must not pre-authorize the next stage.
