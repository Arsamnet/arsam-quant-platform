# Product Requirements

## Bootstrap acceptance

- Paper-only startup and loopback-only internal API
- Strict versioned request contract with trace ID, UTC timestamp, nonce, node ID, symbol, and data
- Deterministic strategy, explicitly disabled AI, fail-closed risk, fake paper execution, and audit
- No live/demo broker order path, remote AI call, paid news dependency, or multi-tenant billing
- Exact decimal financial values, aware UTC time, replay protection, structured non-secret logs
- PostgreSQL/Alembic foundation without requiring PostgreSQL for unit tests
- Automated formatting, lint, strict typing, behavior tests, coverage, pre-commit, and CI

## Quality attributes

Safety takes precedence over availability for new trades. The system must be reproducible,
observable, testable without networks, natively operable on Windows Server, and extensible toward
isolated trading nodes. Performance-sensitive tick handling must never block on remote AI/news work.

## Explicit non-goals

Profit claims, strategy optimization, live trading, demo `OrderSend`, billing, licensing,
multi-tenancy, Redis, paid market/news integrations, and comprehensive monitoring are not part of
version 0.2.0.
