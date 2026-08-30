# Observability

The bootstrap exposes `/health` and emits compact JSON logs containing timestamp, severity, logger,
message, route/status/latency, and available decision/signal/execution/node IDs. It intentionally
does not serialize arbitrary request data, headers, bodies, credentials, API keys, account IDs, or
full authorization values.

Future metrics include process health, last market update/decision, AI latency/error rate, broker
and database connectivity, decision/rejection counts, rejection reasons, open-position state,
drawdown, and spread anomalies. Alerts must distinguish “no new trades” from unsafe management of
already-open positions. Monitoring must not become a production dependency for local safety.
