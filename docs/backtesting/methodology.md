# Backtesting Methodology

Backtests must be event-driven and consume only data that was available at each simulated instant.
The engine will separate immutable market snapshots, strategy state, portfolio/risk state, and an
execution model. The first increment should remain small, deterministic, and AI-independent.

Every result records dataset snapshot/version/hash, strategy and parameter version, code version,
UTC interval, symbols/sessions, deterministic random seed, Bid/Ask source, spread, commission, swap,
slippage, delay, fill assumptions, and known missing data. Economic data must be point-in-time and
must not substitute revised values for historical releases.

Data preparation must guard against look-ahead, future leakage, accidental test-set fitting,
survivorship bias where applicable, and hidden cost assumptions. Research uses training/validation
periods, a locked out-of-sample test, walk-forward analysis, sensitivity checks, and eventually
Monte Carlo perturbation. Metrics include drawdown, distribution of returns, turnover/costs,
exposure, stability, and uncertainty—not only total profit.

If historical AI assessments are added, they are versioned stored fixtures produced at the relevant
historical information boundary; current model output may never impersonate a historical decision.
