# ADR-0002: AI Is Advisory Only

- Status: Accepted
- Date: 2026-08-30

## Context

AI can classify or reason over uncertain context but is non-deterministic, externally hosted, and
exposed to untrusted news content and schema/prompt failures.

## Decision

AI receives a candidate signal and returns only bounded structured advisory fields. It has no
execution adapter, credentials, arbitrary code/URL/tool fields, or authority over volume and risk.
Validated advice proceeds through deterministic risk and the MQL5 validator. Disabled is an
explicit configured state; unexpected unavailable or invalid states reject.

## Alternatives Considered

- Let AI place orders or choose unrestricted size: rejected as unsafe and unauditable.
- Call AI on every tick: rejected for latency, cost, reliability, and time-critical blocking.
- Make AI mandatory for deterministic backtests: rejected because results would not reproduce.

## Consequences

AI can improve context only when available and policy permits. Some trades are missed during faults,
and historical assessments require stored/versioned datasets.

## Security Impact

External text remains untrusted data, strict output validation prevents schema expansion, and no
secret or execution capability enters the AI boundary.

## Testing Impact

Tests use Null/fake clients only and cover unavailable, invalid, extra, conflicting, and bounded
output. The bootstrap suite performs no OpenAI network request.
