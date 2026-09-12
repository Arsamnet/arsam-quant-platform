# MetaTrader 5 Boundaries

`metadata_probe/ReadOnlyMetadataProbe.mq5` remains a separate read-only script. Its completed 0.4.0
compile/calibration evidence does not authorize an order.

`execution_guard/ArsamDemoExecutionGuard.mq5` is the sole reviewed 0.5.0 trade boundary. It polls the
authenticated loopback API, defaults disabled, hard-rejects every non-DEMO account, requires the
exact FIBOGroup identity and conservative limits, persists replay state in `FILE_COMMON`, reconciles
magic/comment broker history, and contains exactly one `OrderSend` call after `OrderCheck`.

The EA requests no broker credential and must never contain or log broker passwords, OpenAI/news
keys, database credentials, or control-plane secrets. Its local execution token is supplied as an
operator input and must not appear in screenshots or committed parameter files.

The 0.5.0 EA has not yet been compiled in Windows MetaEditor. Follow
`docs/runbooks/demo-deployment.md`; require `0 errors, 0 warnings` for the exact source before any
controlled DEMO test. Static scans do not replace compilation and human review.
