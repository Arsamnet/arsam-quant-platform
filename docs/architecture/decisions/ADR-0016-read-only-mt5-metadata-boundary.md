# ADR-0016: Read-Only MT5 Metadata Boundary

- Status: Accepted
- Date: 2026-08-31

## Context

The platform must verify real terminal/account/symbol facts before demo execution, while development
occurs on macOS and the system remains strictly paper-only.

## Decision

Use a reviewed MQL5 script inside an already authenticated Windows terminal to read metadata and
export a versioned offline artifact. It may call read-only hypothetical calculation functions but
contains no order/position mutation path. Python consumes only the exported artifact in 0.4.0; no
official MetaTrader5 dependency or terminal connection enters core imports or tests.

## Alternatives Considered

- Normal cross-platform MetaTrader5 dependency: rejected because official terminal integration is
  Windows-specific and would break offline/macOS installation assumptions.
- Direct broker execution adapter: rejected because acquisition must not create execution authority.
- Guessed broker fixtures: rejected because they provide no calibration evidence.

## Consequences

Real capture requires an operator step on Windows. Offline artifacts are auditable and CI remains
deterministic. Demo execution remains a separate future milestone.

## Security Impact

The probe requests no credentials, persists no raw login, declares a read-only safety marker, and is
scanned for forbidden trade APIs. The lexical scan is defense in depth and does not replace review.

## Testing Impact

Core tests need no terminal/network/credentials. A real release gate later requires MetaEditor
compilation and terminal capture; macOS CI cannot claim either.
