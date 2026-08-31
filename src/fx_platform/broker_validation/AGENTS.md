# Broker Validation Agent Guide

- This boundary is strictly read-only. Never add order submission or position/order mutation APIs.
- Keep MT5/Windows imports isolated; core parsing and validation must work offline on every CI OS.
- Normalize financial text directly to `Decimal` and reject malformed, missing, or non-finite data.
- Preserve UTC acquisition/observation instants and never infer a broker-server UTC offset.
- Unknown required modes, metadata, bits, identity, or freshness fail closed.
- Never persist credentials, raw account logins, or guessed broker values. Tests use synthetic data.
