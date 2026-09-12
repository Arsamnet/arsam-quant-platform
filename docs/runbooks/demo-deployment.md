# Guarded Windows DEMO Deployment and First-Trade Gate

This runbook prepares v0.5.0 for controlled validation against exactly `FIBO Group, Ltd` /
`FIBOGroup-MT5 Server`, USD, retail hedging, leverage 1:100. It is not a release or production
runbook. Windows infrastructure hardening, services, PostgreSQL/Redis, backups, and monitoring are
deliberately deferred.

## 1. Prepare without trading

Start from the reviewed `feat/demo-execution` commit with a clean worktree. Copy `.env.example` to
`.env`; never commit it. Set:

```text
FX_TRADING_MODE=demo
FX_BIND_HOST=127.0.0.1
FX_DEMO_EXECUTION_ENABLED=true
FX_DEMO_EXECUTION_SECRET=<unique 32+ character local secret>
FX_DEMO_NODE_ID=local-demo-node
```

Do not change the reviewed broker/server/currency/mode/leverage/symbol/volume/position/SL/TP/TTL/
magic values. The Python switch is a startup barrier: setting it false must reject demo startup.

Run in PowerShell:

```powershell
./scripts/deploy-demo-node.ps1 -Mt5DataPath "<MT5 data folder>" -InstallEA
```

The script verifies Windows, clean Git state, locked dependencies, quality gates, `.env`, validated
configuration, and the explicit MT5 data path. It can copy only EA source. It never launches MT5,
arms the EA, copies credentials, or places an order.

## 2. Compile and install

Open the copied `MQL5/Experts/ArsamQuant/ArsamDemoExecutionGuard.mq5` in MetaEditor. Compile the exact
reviewed source. Stop unless the result is `0 errors, 0 warnings`; retain sanitized output. Do not
claim this gate from CI or macOS.

The optional wrapper runs the same gate and fails on any warning:

```powershell
./scripts/compile-mt5-execution-guard.ps1 -MetaEditorPath "<path-to-metaeditor64.exe>"
```

In MT5, allow WebRequest only for `http://127.0.0.1:8000`. Attach the EA to one chart with:

```text
EnableDemoExecution=false
LocalApiBaseUrl=http://127.0.0.1:8000
ExecutionToken=<same local secret; never log/screenshot it>
NodeId=local-demo-node
MagicNumber=5050001
```

Confirm the chart says `DEMO EXECUTION DISABLED`.

## 3. Start and verify Python

```powershell
./scripts/start-demo-node.ps1
./scripts/check-demo-node.ps1
```

The console must show DEMO, execution enabled, LIVE forbidden, and `127.0.0.1`. Ensure no other
interface is listening. The EA switch stays false.

## 4. Negative gates before any order

Capture sanitized evidence for each rejection, with no account login or secret:

1. `FX_DEMO_EXECUTION_ENABLED=false` prevents demo startup.
2. `EnableDemoExecution=false` prevents polling/submission.
3. Synthetic/controlled intents reject volume `0.02`, missing SL, missing TP, expiry, duplicate
   nonce/execution ID, and wrong expected server configuration.
4. Automated tests prove `FX_TRADING_MODE=live` startup rejection, while repository checks verify
   the EA retains its hard non-DEMO rejection. The real terminal negative gate remains a Windows
   operator check; never connect the EA to a live account for a test.

Restore reviewed settings, restart Python, verify outbox has no unresolved claim, and independently
read from MT5: DEMO mode, exact company/server, USD, hedging, leverage 100, connected/trading/
automated trading allowed, and EURUSD trade-enabled.

## 5. Exact first trade

Only after approval, set `EnableDemoExecution=true`. Submit one normal `/v1/decision` request—not a
manual execution endpoint—with EURUSD, market direction from strategy, volume `0.01`, valid
broker-side SL and TP, current account/market data, open position count zero, and reviewed spread.

Expected path:

```text
RiskEngine APPROVED -> ExecutionIntent -> SQLite outbox -> authenticated EA poll
-> EA guards -> journal -> OrderCalcMargin -> OrderCheck -> OrderSend
-> result -> order/deal/position reconciliation
```

Record sanitized execution/intent IDs, retcode, order/deal IDs, fill volume/price, SL/TP, position,
and reconciliation. Do not commit raw terminal logs or account number.

## 6. Replay, kill, and restart

Replay the same logical decision. Verify no second broker order/position. Disable the Python switch
(demo startup must fail), then disable the EA switch and confirm neither path submits. After a fully
reconciled result, restart API and EA; verify the journal loads, the broker position is recognized,
and replay still does not submit.

## 7. Symbol progression and stop condition

After EURUSD passes execution, reconciliation, replay, both kill switches, and restart, repeat one
0.01 GBPUSD test. Test USDJPY last and only with a fresh explicit directed JPY-to-USD conversion
accepted by RiskEngine. Never weaken conversion policy.

On any `unknown`, mismatched ID/fact, uncertain broker history, unexpected position, or failed
result report: disable the EA, leave Python blocked, preserve sanitized evidence, and reconcile
manually. Never retry `OrderSend` automatically.
