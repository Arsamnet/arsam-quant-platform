# Observability

The bootstrap exposes `/health` and emits compact JSON logs containing timestamp, severity, logger,
message, route/status/latency, and available run/dataset/decision/signal/risk/execution/trade/node
IDs. Backtests log one INFO completion summary and DEBUG trace events while their canonical result
retains the immutable audit sequence. Broker validation may log constrained snapshot/contract
fingerprints, validation symbol, and aggregate status; it does not log snapshot contents, broker
account identifiers, or calculation payloads. Logging intentionally does not serialize arbitrary request or
historical data, headers, bodies, credentials, API keys, account IDs, or full authorization values.

Future metrics include process health, last market update/decision, AI latency/error rate, broker
and database connectivity, decision/rejection counts, rejection reasons, open-position state,
drawdown, and spread anomalies. Alerts must distinguish “no new trades” from unsafe management of
already-open positions. Monitoring must not become a production dependency for local safety.
