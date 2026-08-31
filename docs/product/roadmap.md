# Roadmap

1. **0.1 bootstrap (complete):** paper-only vertical slice, safety boundaries, tests, docs, CI.
2. **0.2 risk hardening (complete):** early symbol rejection, broker-independent static metadata,
   account-relative daily loss, explicit currency conversion, per-symbol spread, and HMAC review.
3. **0.3 deterministic backtest (complete):** event-driven engine, point-in-time data fixture,
   Bid/Ask spread,
   commission/slippage assumptions, reproducible snapshot/version/seed, and out-of-sample split.
4. **0.4 read-only broker contract validation (complete in code):** strict offline MT5 metadata
   schema/import, canonical snapshots, dual fingerprints/diff, guarded symbol mapping, severity-rich
   validation, calculation calibration foundation, read-only probe, safety scan, and synthetic tests.
5. **Recommended next—real broker calibration:** independently compile the probe in MetaEditor,
   capture intended FIBOGroup demo account metadata for EURUSD/GBPUSD/USDJPY, hand-reconcile profit/
   margin cases, validate archive provenance, and review contract drift. No execution.
6. **Demo validation:** add position state and signed localhost intent polling only after calibration,
   then explicit demo mode after operational approval, fault injection,
   reconciliation, and kill-switch runbooks. Live remains disabled.
7. **Research expansion:** economic calendar fixture/provider, news classification isolation,
   walk-forward/Monte Carlo evaluation, and versioned AI assessment datasets.
8. **Commercialization:** separately reviewed control plane, node identity, entitlements, secure
   updates, telemetry, tenant isolation, and billing. Broker passwords stay on trading nodes.

Each stage needs its own acceptance criteria and must not pre-authorize the next stage.
