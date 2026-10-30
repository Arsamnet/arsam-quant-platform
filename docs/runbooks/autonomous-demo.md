# Autonomous AI-Assisted DEMO Runbook

This runbook is for v0.6 engineering validation on the same reviewed FIBOGroup DEMO account. It does
not authorize LIVE trading and does not claim that the current example strategy is profitable.

## 1. Safety prerequisites

Start from a clean reviewed v0.6 commit. The v0.5 guarded execution API/outbox and
ArsamDemoExecutionGuard.mq5 must already be installed and known-good.

The execution guard remains the only component that may call OrderSend. Keep
EnableDemoExecution=false until the snapshot source, OpenAI advisory path, and supervisor have
passed the non-trading checks below.

## 2. Install and compile the read-only autonomous probe

On Windows, run:

    ./scripts/install-mt5-autonomous-probe.ps1 -Mt5DataPath "<MT5 data folder>"

    ./scripts/compile-mt5-execution-guard.ps1 `
      -MetaEditorPath "<path-to-metaeditor64.exe>" `
      -EaSourcePath "<MT5 data folder>\MQL5\Experts\ArsamQuant\ArsamAutonomousSnapshotProbe.mq5"

Stop unless MetaEditor reports exactly 0 errors, 0 warnings.

Attach ArsamAutonomousSnapshotProbe to one chart with the reviewed defaults:

    RequestedSymbols=EURUSD,GBPUSD,USDJPY
    DecisionTimeframe=PERIOD_M15
    RefreshSeconds=1
    OutputFile=arsam_autonomous_snapshot_1_0.json

The probe is read-only. It writes under the terminal MQL5\Files directory and never arms or places
an order.

## 3. Configure v0.6 autonomous DEMO

Keep secrets only in the local .env:

    FX_TRADING_MODE=demo
    FX_BIND_HOST=127.0.0.1
    FX_DEMO_EXECUTION_ENABLED=true
    FX_DEMO_EXECUTION_SECRET=<unique 32+ character local secret>

    FX_AI_MODE=openai
    FX_AI_REQUIRED=true
    FX_OPENAI_API_KEY=<environment-owned key>
    FX_OPENAI_MODEL=<reviewed model name>
    FX_OPENAI_TIMEOUT_SECONDS=8

    FX_AUTONOMOUS_DEMO_ENABLED=true
    FX_AUTONOMOUS_SNAPSHOT_PATH=<MT5 data folder>\MQL5\Files\arsam_autonomous_snapshot_1_0.json
    FX_AUTONOMOUS_POLL_INTERVAL_SECONDS=1
    FX_AUTONOMOUS_MAX_SNAPSHOT_AGE_SECONDS=15
    FX_AUTONOMOUS_ACCOUNT_ID=fibo-demo-usd-local

Do not change the reviewed DEMO broker/server/currency/leverage/symbol/volume/position/SL/TP/magic
limits.

## 4. Validate the snapshot without AI or execution

With the probe running:

    uv run fx-autonomous-demo --validate-snapshot

This only parses the local file and checks broker/server, DEMO mode, hedging mode, leverage,
permissions, exact symbol set, trade mode, financial values, and tick age. It does not call OpenAI,
RiskEngine, the outbox, or MT5 execution.

Any failure is a stop condition.

## 5. Start the existing local execution API

In terminal 1:

    ./scripts/start-demo-node.ps1

Verify that the local health endpoint reports status=ok, trading_mode=demo, and ai_mode=openai.
Keep the execution EA disabled.

## 6. AI-only validation

Before RiskEngine or outbox testing, validate one real OpenAI advisory with the execution EA still
disabled:

    uv run fx-autonomous-demo --validate-ai EURUSD

This command validates the same fresh local MT5 snapshot, creates the deterministic strategy
candidate, and calls only the structured OpenAI advisory boundary. It does not construct RiskEngine,
does not open the SQLite outbox, and cannot call MT5 execution. The safe JSON result explicitly
reports risk_engine_called=false, outbox_called=false, and execution_called=false.

Provider/schema failure is a stop condition.

## 7. Controlled one-cycle decision validation

Only after AI-only validation succeeds:

    uv run fx-autonomous-demo --once

This runs the normal strategy/AI/risk workflow. If RiskEngine approves, it can place one intent in
the durable DEMO outbox. Because the execution EA is still disabled, no broker order is expected.
Inspect local logs and outbox/status before proceeding. Do not blindly repeat an ambiguous cycle.

If an approved intent was queued during this check, let it expire and verify/reconcile its durable
state before arming the EA.

## 8. Autonomous DEMO burn-in

Only after explicit operator approval, enable the existing execution EA and start:

    ./scripts/start-autonomous-demo.ps1

Expected path:

    read-only MT5 snapshot
    -> deterministic strategy candidate
    -> schema-constrained OpenAI advisory
    -> RiskEngine
    -> durable SQLite intent
    -> authenticated localhost execution guard
    -> broker DEMO
    -> reconciliation

The supervisor will not create another autonomous intent while an execution is unresolved or while
the account snapshot reports an open position. A new decision is considered at most once per symbol
per observed bar in the running process.

## 9. Stop conditions

Immediately disable the execution EA and stop the supervisor on any broker/server/account identity
mismatch, stale or malformed snapshot, unexpected symbol/trade-mode change, required-AI failure,
unresolved execution state, unexpected broker position, duplicate/ambiguous submission evidence, or
any LIVE account/mode indication.

Never automatically retry an ambiguous broker outcome.

## 10. Current limitation

The deterministic strategy remains PreviousCloseMomentumStrategy, which exists to prove the
architecture and has no profitability claim. v0.6 autonomous validation must therefore be evaluated
first for safety, determinism, reconciliation, duplicate suppression, AI availability behavior, and
operational stability. Strategy research and statistical edge validation are separate work.
