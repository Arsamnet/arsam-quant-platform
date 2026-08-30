# Architecture

Arsam Quant Platform uses pragmatic Clean/Hexagonal Architecture. Domain code depends on no web,
database, AI, news, MetaTrader, or broker framework. Application orchestration depends on domain
types and protocols; adapters and FastAPI supply external implementations.

```text
Market/Account Snapshot -> Deterministic Strategy -> Candidate Signal
                                             |-> AI Advisor (advisory only)
                                             |-> Economic Calendar
                                             v
                                      Fail-Closed Risk Engine
                                             v
                                      Paper Execution Intent
                                             v
                                 Final Validator / Future MQL5 EA
                                             v
                                           Broker
```

Risk can reject every candidate regardless of AI output. MQL5 will be an independent last-line
guard; version 0.1.0 includes no order-sending MQL5 code. The current API, fake executor, and audit
repository run within one loopback-only trading node.

Detailed views and decisions:

- [System context](docs/architecture/system-context.md)
- [Trading node and v1 contract](docs/architecture/trading-node.md)
- [Future SaaS boundary](docs/architecture/future-saas.md)
- [Architecture Decision Records](docs/architecture/decisions/README.md)
