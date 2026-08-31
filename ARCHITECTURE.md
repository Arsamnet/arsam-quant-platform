# Architecture

Arsam Quant Platform uses pragmatic Clean/Hexagonal Architecture. Domain code depends on no web,
database, AI, news, MetaTrader, or broker framework. Application orchestration depends on domain
types and protocols; adapters and FastAPI supply external implementations.

```text
Request/node/symbol validation -> SymbolSpecification -> Deterministic Strategy
                                                            |-> AI Advisor (advisory only)
                                                            |-> Economic Calendar
                                                            v
                                          Fail-Closed Risk Engine
                                          | symbol defense in depth
                                          | account-currency exposure
                                          | per-symbol spread policy
                                                            v
                                             Paper Execution Intent
                                                            v
                                        Final Validator / Future MQL5 EA
                                                            v
                                                          Broker
```

Risk can reject every candidate regardless of AI output. MQL5 will be an independent last-line
guard; version 0.3.0 includes no order-sending MQL5 code. The current API, fake executor, and audit
repository run within one loopback-only trading node.

Version 0.3.0 adds an outer `fx_platform.backtesting` composition. It streams immutable historical
bars through a monotonic UTC clock, the existing strategy/null-advisory/risk pipeline, a no-network
simulated broker, in-memory portfolio accounting, immutable ledger, and canonical report. It imports
domain/application contracts but domain code imports no simulation infrastructure. PostgreSQL is
not required.

```text
Historical CSV -> validated event stream -> BacktestClock -> MarketSnapshot
                                                        -> StrategyEvaluator
                                                        -> Null AI/calendar
                                                        -> RiskEngine
                                                        -> paper ExecutionIntent
                                                        -> SimulatedBroker (next open)
                                                        -> Portfolio / ledger / report
```

No complete dataset or future-aware collection crosses the strategy boundary. Detailed timing,
Bid/Ask, cost, and ambiguity semantics are in
[the backtesting methodology](docs/backtesting/methodology.md).

The bootstrap uses reviewed static `SymbolSpecification` values. The domain and application depend
only on a metadata-provider protocol, so a future MT5 adapter may populate the same model after its
contract data is independently verified. No MT5 connection exists in this version.

Detailed views and decisions:

- [System context](docs/architecture/system-context.md)
- [Trading node and v1 contract](docs/architecture/trading-node.md)
- [Future SaaS boundary](docs/architecture/future-saas.md)
- [Architecture Decision Records](docs/architecture/decisions/README.md)
