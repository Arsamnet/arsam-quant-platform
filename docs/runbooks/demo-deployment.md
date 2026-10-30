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

The wrapper removes any existing sibling `.ex5` first, then requires one exact clean `Result` line
and a newly created non-empty `.ex5`. It records MetaEditor's process exit code as evidence but does
not treat that code as authoritative because the reviewed FIBO installation returns `1` after a
successful compile.

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
0.01 GBPUSD test. Test USDJPY last and only through this reviewed flow:

1. With the EA disabled, obtain a fresh read-only USDJPY broker Bid/Ask snapshot.
2. Revalidate broker, server, USD account, DEMO mode, hedging mode, leverage, and USDJPY identity.
3. In the normal `/v1/decision` request, explicitly request `JPY -> USD` and supply the exact
   inverse USDJPY pair currencies, Bid, Ask, and observed-at UTC time in
   `inverse_conversion_quotes`.
4. Confirm the API derives the stop-loss exposure rate as
   `rate = Decimal(1) / USDJPY bid`. The reviewed loss-side calibration requires Bid here;
   positive/profit conversion is separate and corresponds to `1 / ask` in the same evidence.
5. Retain the request, quote provenance, timestamp, method, side, and resulting directed rate as
   sanitized evidence.
6. Require the normal freshness/future-skew checks and pass only the directed JPY-to-USD rate into
   `RiskEngine`.
7. Stop on any pair/currency mismatch, stale/future quote, invalid price, missing conversion, or
   multiple applicable conversion candidates. Do not substitute Ask, midpoint, last price,
   arbitrary inversion, or any cross/multi-hop rate for this reviewed stop-loss derivation.
8. Complete deterministic and risk negative tests while the EA remains disabled.
9. Only after explicit approval, arm the EA for one 0.01 USDJPY DEMO execution.

The exact reviewed EA source must receive a fresh Windows MetaEditor compile with `0 errors,
0 warnings` after any trigger-side validation change. Reinstall that exact compiled artifact before
resuming this sequence; no earlier MetaEditor artifact covers the changed source.

On any `unknown`, mismatched ID/fact, uncertain broker history, unexpected position, or failed
result report: disable the EA, leave Python blocked, preserve sanitized evidence, and reconcile
manually. Never retry `OrderSend` automatically.

## 8. Sanitized USDJPY preflight block

With the EA still disabled, a fresh USDJPY read-only observation showed a 9-tick spread. The old
cross-symbol absolute stop distance was only 1 USDJPY tick, which placed the illustrative SELL stop
inside the current Ask. Execution was deliberately blocked before arming the EA, and no order was
placed. Remediation required both a tick-normalized 100-tick example-strategy stop and MQL5 SL/TP
validation on the position trigger side (Bid for BUY, Ask for SELL). Do not retain raw broker
snapshots or account identifiers in the repository.

## 9. Sanitized validation completed before inverse-quote implementation

The reviewed environment was `FIBO Group, Ltd` / `FIBOGroup-MT5 Server`, USD DEMO
(`trade_mode_code=0`), retail hedging (`margin_mode_code=2`), leverage 100, hard volume cap 0.01,
and one open position maximum. LIVE remained forbidden.

- Commit `bc11030` corrected `OrderCheck` handling after FIBO returned Boolean success,
  `GetLastError()=0`, `check.retcode=0`, and `comment=Done`. `OrderSend` continues to use broker
  trade-server retcodes.
- Commit `94d5bdb` allowed only `1e-12` broker-price serialization residue in durable result matching
  (for example `1.1472800000000001` versus broker-normalized `1.14728`). Volume and identity remain
  exact and a real one-tick price mismatch still rejects.
- EURUSD SELL 0.01 completed through the normal decision path, broker-side SL/TP, ticket/order
  `33833840`, durable `position_confirmed`, duplicate replay without durable mutation, both kill
  switches, API restart, and EA restart without a second order. It was manually closed: trade P/L
  `-0.48 USD`, commission `-0.06 USD`, net account effect `-0.54 USD`.
- GBPUSD request `a24fa1f3-d4d6-4354-b32a-8960534c9ab5`, execution
  `23a990c3-18b2-52e5-8adb-b870e27d381b`, SELL 0.01 reached broker ticket `33842795`, deal
  `24196918`, executed price `1.33843`, SL `1.33946`, TP `1.33646`, confirmed broker protection,
  zero pending orders, and durable counts `position_confirmed=2`, `rejected=1`. It was manually
  closed: P/L `+0.14 USD`, commission `-0.08 USD`, swap `0`.
- After both closes the account showed starting balance `10000.00 USD`, current balance
  `9999.52 USD`, trade Profit `-0.34 USD`, Commission `-0.14 USD`, Swap/Fee `0`, net realized effect
  `-0.48 USD`, and zero open positions.
- USDJPY used previous D1 close `156.868`. With no `JPY -> USD` conversion, request
  `9ec5f84f-467e-46b8-afc8-51164530b843` correctly returned `risk_rejected` /
  `conversion_rate_unavailable` with no execution ID or status.

These figures validate execution and fail-closed paths only; they are not strategy-performance or
profitability evidence. No USDJPY broker execution has passed. Local inverse-quote implementation,
deterministic/risk-negative validation, and quality gates completed with 427 tests passing, 96.07%
branch coverage, Ruff format/check, strict mypy, and pre-commit. Remaining work is Windows
deployment of this change and one explicitly approved 0.01 USDJPY DEMO execution followed by
reconciliation, replay, kill-switch, and restart checks as applicable. Only then may final v0.5.0
merge/tag be considered.
