# MQL5 DEMO Execution Guard

`mt5/execution_guard/ArsamDemoExecutionGuard.mq5` is the sole reviewed production-code trade API
boundary. The read-only metadata probe remains separate and contains no trade API.

Before its single `OrderSend` call, the EA requires: both kill switches, terminal connectivity and
trade permissions, DEMO account mode, exact FIBO company/server, USD, retail hedging, leverage 100,
magic 5050001, an exact `http://127.0.0.1:<port>` URL, a 32+ character token, authenticated node
identity, market order, EURUSD/GBPUSD/USDJPY,
unexpired/non-future request, unseen IDs/nonce/fingerprint, trade-enabled symbol, 0.01 maximum and
broker volume grid, tick-aligned directional SL/TP, stops/freeze distance, reviewed spread,
fewer than one Arsam position, sufficient calculated/free margin, and successful `OrderCheck`.

The hard DEMO check has no input and no bypass. Expected broker identity, future-skew/deviation
policy, and exposure ceilings are constants, not operator-overridable settings. The EA never logs
its token or account login.

The append-only `FILE_COMMON/ArsamQuant/demo-execution-v050.csv` journal stores only correlation and
trade facts, never credentials. A marker such as `A5-<24 hex>` plus magic number links journal
entries to positions and deal history. A claim is journaled before submission and a submitted state
is flushed before calling the broker. Restart reconciliation blocks on uncertainty.

This source has not yet passed the Windows MetaEditor gate. Release evidence must show `0 errors,
0 warnings` for the exact reviewed source. The lexical CI scan is defense in depth, not compilation
or formal verification.
