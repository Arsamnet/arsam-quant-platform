# ADR-0021: Cross-Platform Development and Windows MT5 Validation

- Status: Accepted
- Date: 2026-08-31

## Context

Development and routine CI must work on macOS/Linux/Windows, while a native MetaTrader terminal and
official Python integration are Windows trading-node concerns.

## Decision

Keep acquisition in isolated MQL5 source and exchange a portable file. Parsing, normalization,
mapping, validation, diff, CLI, and tests are pure offline Python. Do not add MetaTrader5 as a normal
or optional project dependency in 0.4.0 because the MQL5 exporter supplies the needed authority with
a smaller dependency and credential surface.

## Alternatives Considered

- Skip tests when MT5 is absent: rejected because core correctness cannot depend on infrastructure.
- Mock the official package throughout core code: rejected because import/platform risks remain and
  mocks do not prove terminal behavior.
- Claim compile readiness from source review: rejected because only MetaEditor can validate it.

## Consequences

All ordinary quality gates remain service-free. Actual probe compilation/capture is a separate
Windows validation activity and remains a release limitation until independently performed.

## Security Impact

No broker credentials, package-native connection, or network access enter CI/macOS development.
Snapshot files are still untrusted inputs and receive strict validation.

## Testing Impact

Synthetic cross-platform tests run unconditionally. MetaEditor compilation and real demo capture
must be reported from separate evidence rather than skipped or represented as CI success. The 0.4.0
Windows compile gate and distinct official capture pair were completed and recorded by 2026-09-06.
