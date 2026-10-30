# MetaTrader 5 Boundaries

`metadata_probe/ReadOnlyMetadataProbe.mq5` remains the offline read-only broker metadata and
calculation probe used for contract validation.

`autonomous_probe/ArsamAutonomousSnapshotProbe.mq5` is a separate v0.6 read-only EA. It
continuously exports broker/account/market observations for the Python autonomous supervisor.
It has no order, position, or pending-order mutation API and must compile with `0 errors, 0 warnings`
before Windows DEMO validation.

`execution_guard/ArsamDemoExecutionGuard.mq5` remains the sole reviewed trade boundary. It polls
the authenticated loopback API, defaults disabled, hard-rejects every non-DEMO account, requires
the exact FIBOGroup identity and conservative limits, persists replay state in `FILE_COMMON`,
reconciles magic/comment broker history, and contains exactly one `OrderSend` call after
`OrderCheck`.

The autonomous probe and execution guard are intentionally separate: market/account observation
cannot place an order, and the execution guard never connects to OpenAI. OpenAI/news keys,
database credentials, broker passwords, and control-plane secrets must never enter MQL5 files or
logs.

The v0.5 execution guard completed reviewed Windows MetaEditor and controlled DEMO validation.
The new v0.6 autonomous probe still requires its own fresh Windows MetaEditor compile and runtime
snapshot validation. Follow `docs/runbooks/autonomous-demo.md`.
