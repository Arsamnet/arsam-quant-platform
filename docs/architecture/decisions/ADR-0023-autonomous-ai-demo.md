# ADR-0023: Guarded autonomous AI-assisted DEMO supervisor

- Status: Accepted
- Date: 2026-10-30

## Context

Version 0.5.0 proved the guarded DEMO execution path from a reviewed decision through the durable
SQLite outbox, localhost execution API, MQL5 guard, broker execution, and reconciliation. It still
required an operator or test harness to submit each decision. The next engineering goal is to let
the reviewed DEMO account generate decisions continuously without giving an AI model or the MQL5
execution boundary independent trading authority.

## Decision

Version 0.6.0 adds a separate read-only MQL5 autonomous snapshot probe and a Python autonomous
supervisor.

The probe continuously exports only local broker/account/market observations: broker/server
identity, terminal connectivity, DEMO account mode, leverage, balance/equity, daily realized P/L,
open-position count, Bid/Ask, previous D1 close, current decision-bar identity, trade mode, and tick
age. It contains no order mutation API.

The Python file adapter rejects malformed, partial, stale, disconnected, non-DEMO, wrong-broker,
wrong-server, wrong-currency, wrong-leverage, wrong-symbol-set, or non-trade-enabled observations.

The supervisor:

- evaluates each symbol at most once per observed decision bar in one process;
- generates deterministic request IDs/nonces from node, symbol, and bar identity;
- will not read a new snapshot while the durable execution outbox has unresolved work;
- does not request a new decision while the account reports an open position;
- stops the cycle after the first DEMO intent is durably queued;
- derives only the already-reviewed exact inverse USDJPY conversion when needed;
- never retries the same bar automatically after an ambiguous exception in that process.

OpenAI is integrated through the Responses API behind the existing AiAdvisor boundary. The model
receives only bounded snapshot/candidate data and must return the strict advisory schema. It has no
tool access, broker credential, execution token, or order API. RiskEngine retains final
application-side rejection authority, and the existing MQL5 guard remains the sole OrderSend
boundary.

Autonomous startup is allowed only when all of these are true:

- trading mode is demo;
- guarded DEMO execution is explicitly enabled;
- OpenAI mode has environment-owned credentials/model configuration;
- FX_AI_REQUIRED=true;
- FX_AUTONOMOUS_DEMO_ENABLED=true.

Live mode remains forbidden.

## Alternatives Considered

Directly connecting the execution EA to OpenAI was rejected because it would collapse advisory and
execution trust boundaries.

Letting the model produce raw order size, SL/TP, or execution commands was rejected. Deterministic
strategy and risk code continue to own those values.

Using remote market data instead of the reviewed MT5 account snapshot was rejected for this phase
because broker/account state must remain the execution source of truth.

Allowing multiple autonomous intents in parallel was rejected because v0.6 keeps the reviewed
single-position DEMO exposure policy.

## Consequences

The platform can now run a bounded autonomous DEMO decision loop once the Windows probe and OpenAI
configuration have been independently validated. The existing example previous-close strategy is
still illustrative; autonomous operation proves orchestration and safety behavior, not statistical
edge or profitability.

A supervisor process restart can re-evaluate a previously rejected bar because the per-bar memory is
process-local. An approved prior bar still cannot create a second broker order because deterministic
request identity and durable outbox uniqueness suppress it. Persisting rejected/no-signal bar state
is a future hardening item.

## Security Impact

Secrets remain environment-owned and never enter the MT5 snapshot file or model input. The OpenAI
client uses only the fixed HTTPS Responses API endpoint, disables response storage for these
requests, requests a strict JSON schema, and translates provider/network failure into unavailable
advice. When AI is required, unavailable or invalid advice prevents execution.

The read-only probe must continue to contain no trade mutation API. The execution guard remains
default-off and LIVE remains forbidden independently in Python and MQL5.

## Testing Impact

Unit coverage must include schema-constrained AI requests, provider failure, malformed model output,
snapshot identity/freshness rejection, tick staleness, unresolved-outbox blocking, open-position
blocking, bar deduplication, one-intent-per-cycle behavior, and USDJPY inverse conversion.

Before autonomous DEMO burn-in, the exact new MQL5 probe source must compile in Windows MetaEditor
with 0 errors, 0 warnings, the snapshot-only CLI validation must pass, and the normal cross-platform
quality/CI gates must be green.
