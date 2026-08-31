# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
uses Semantic Versioning during pre-production.

## [Unreleased]

## [0.3.0] - 2026-08-31

### Added

- Deterministic event-driven backtest engine reusing the existing strategy, null advisory/calendar,
  fail-closed Risk Engine, paper intent, and symbol specification boundaries.
- Strict immutable historical Bid OHLC plus fixed-spread CSV contract, UTC validation, canonical
  dataset metadata/checksum, point-in-time conversion replay, and chronological three-way splits.
- Monotonic historical clock, next-bar-open simulated broker, explicit Bid/Ask fills, deterministic
  commission/slippage, conservative SL/TP ambiguity, portfolio accounting, and immutable trade ledger.
- Canonical run/configuration fingerprints and JSON report with deterministic IDs, realized-balance
  metrics, open-position equity, audit events, and a synthetic EURUSD golden fixture.
- Local `fx-backtest` CLI plus comprehensive unit, integration, regression, and no-future-data tests.
- ADRs 0011–0015 and complete backtesting data, execution, methodology, and reproducibility docs.

### Changed

- Prepare package and API health version 0.3.0 without creating a tag or release.
- Share directed currency conversion validation between risk and simulated portfolio accounting.
- Extend constrained structured-log trace fields for backtest run/dataset/risk/trade identities.

### Security

- Backtests perform no network, broker, MT5, PostgreSQL, external-AI, or non-paper execution.
- Reject malformed, non-finite, duplicate, reverse-ordered, naive-time, or schema-invalid historical
  data and fail closed when symbol, spread, or directed conversion metadata is insufficient.

## [0.2.0] - 2026-08-30

### Added

- Broker-independent `SymbolSpecification` and a static paper metadata provider for EURUSD,
  GBPUSD, and USDJPY.
- Explicit directed currency-conversion inputs and deterministic account-currency risk calculation.
- Regression coverage for every manually validated runtime behavior and combined risk failures.
- ADRs for early symbol validation, relative daily loss, symbol metadata, currency conversion, and
  per-symbol spread policy.

### Changed

- Prepare package version 0.2.0.
- Reject unknown symbols before strategy, AI, calendar, risk, or execution while preserving the
  Risk Engine's independent allowlist defense.
- Replace the absolute-only daily loss limit with a balance fraction and optional absolute cap.
- Replace the global absolute spread threshold with per-symbol maximum spread ticks.
- Add USD account-currency defaults and optional conversion-rate inputs to the compatible v1 wire
  contract.

### Security

- Strictly validate HMAC-SHA256 digest encoding and length before constant-time byte comparison.
- Prove raw-body modification rejection and replay protection independent of valid HMAC.
- Fail startup when retired `FX_MAX_DAILY_LOSS` or `FX_MAX_SPREAD` settings are present.

## [0.1.0] - 2026-08-30

### Added

- Initial paper-only engineering bootstrap, domain/application boundaries, local API, fake executor,
  persistence scaffolding, deterministic tests, CI, and documentation foundation.
