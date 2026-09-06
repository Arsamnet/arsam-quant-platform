# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
uses Semantic Versioning during pre-production.

## [Unreleased]

## [0.4.0] - 2026-09-06

### Added

- Strict schema-1.0 read-only MT5 metadata interchange, immutable broker/account/terminal/symbol and
  calculation snapshots, direct Decimal/UTC normalization, and bounded offline importer.
- Separate canonical full-snapshot and static/calculation-contract SHA-256 fingerprints plus a
  deterministic contract/dynamic diff.
- Fail-closed `SymbolSpecification` mapper and deterministic PASS/INFO/WARNING/BLOCKING validation
  reports covering identity, freshness, calculation modes, currencies, ticks/points, volume grids,
  quotes, modes/unknown bits, stops/freezes, and account hedging/netting state.
- Fingerprinted absolute/relative calibration tolerances and read-only BUY/SELL `OrderCalcProfit`
  comparison; `OrderCalcMargin` evidence archival remains outside RiskEngine.
- Offline `fx-mt5-import`, `fx-broker-validate`, and `fx-broker-diff` commands with canonical file
  artifacts and nonzero malformed/blocking exits.
- Read-only MQL5 metadata/calculation probe, forbidden executable trade-API safety scan, synthetic
  non-broker fixtures, comprehensive cross-platform tests, ADRs 0016–0021, and broker documentation.

### Changed

- Prepare package/API version 0.4.0 without creating a tag, release, broker connection, or execution
  capability; preserve deterministic 0.3 backtesting behavior with version-derived identities.
- Promote canonical JSON/fingerprint primitives to shared package infrastructure.
- Extend constrained structured-log fields with snapshot/contract fingerprints and validation status.

### Security

- No order submission/modification API or broker credentials enter code, tests, snapshots, or logs;
  official Windows-only MetaTrader5 is not a project dependency.
- Strictly reject duplicate/unknown/missing/malformed snapshot structure, JSON financial numbers,
  non-finite decimals, naive timestamps, unknown required capabilities, stale evidence, and trusted
  fingerprint mismatch.
- Independently compile the read-only probe in Windows MetaEditor with `0 errors, 0 warnings`, then
  capture and validate two real FIBOGroup demo observations for EURUSD, GBPUSD, and USDJPY with no
  blocking findings and an unchanged contract fingerprint.
- Keep USDJPY conversion-dependent P/L and full margin equivalence explicitly outside the 0.4.0
  claims; the completed read-only calibration grants no demo/live execution authority.

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
