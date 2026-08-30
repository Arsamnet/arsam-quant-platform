# System Context

The bootstrap system boundary is one Windows trading node. MetaTrader 5 will eventually exchange a
signed versioned JSON contract with a Python API on `127.0.0.1`. Python owns data normalization,
strategy orchestration, optional advisory calls, deterministic risk, persistence, and observability.
The MQL5 EA independently owns final validation and future broker interaction.

External actors and systems are the operator, MT5/broker, future market/calendar/news providers,
OpenAI, local PostgreSQL, and a future SaaS control plane. All external content is untrusted. The
domain depends on none of these systems; adapters translate their data into validated point-in-time
models.

Version 0.1.0 has no MT5 process connection, broker order path, remote AI request, or public API.
