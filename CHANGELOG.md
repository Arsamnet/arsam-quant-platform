# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
uses Semantic Versioning during pre-production.

## [Unreleased]

### Added

- Explicit audited exact-pair inverse conversion input for schema 1.0, retaining broker symbol,
  pair currencies, Bid/Ask, UTC observation, `inverse_exact_pair`/Bid loss-side provenance, and the
  final directed risk rate in deterministic request identity. Cross-rate inference remains
  forbidden.
- Immutable schema-1.0 execution intents/results with request/risk fingerprints, market-only order
  type, exact decimal strings, UTC times, strategy/risk identities, and explicit reconciliation.
- Atomic synchronized SQLite DEMO outbox with durable execution/intent/request/nonce/fingerprint
  uniqueness, claim-once delivery, strict result transitions, restart persistence, and fail-closed
  unresolved-state blocking.
- Authenticated loopback-only demo next/result/reconcile/status endpoints and non-secret node status.
- Default-off `ArsamDemoExecutionGuard.mq5`, the sole reviewed trade boundary, with fixed FIBOGroup
  DEMO identity, 0.01 lot/one-position caps, required broker SL/TP, spread/grid/stops/freeze/margin/
  `OrderCheck` gates, FILE_COMMON journal, magic/comment correlation, and no automatic retry.
- Windows interactive deployment/start/check/install scripts, ADR-0022, execution/reconciliation
  documentation, first-trade/negative/replay/kill/restart runbook, and comprehensive tests.
- Version-controlled USDJPY intent-price-drift negative-test harness with a single synthetic DEMO
  decision, a >10-point drift proof, an independent pre-OrderCheck SELL stop-direction backstop,
  durable rejection/count verification, and explicit no-retry handling.

### Changed

- Prepare development version 0.5.0 while preserving paper behavior and deterministic backtests.
- Complete the full controlled EURUSD execution/reconciliation/replay/kill/restart validation, then
  complete the required GBPUSD follow-up execution/protection/reconciliation gate. This is
  execution-path evidence, not strategy-profitability evidence; GBPUSD did not independently repeat
  the full replay/restart/kill-switch suite.
- Confirm the USDJPY missing-conversion negative gate returns `conversion_rate_unavailable` without
  execution, then complete the controlled inverse-conversion USDJPY DEMO execution/reconciliation
  path and the post-remediation `intent_price_drift_exceeded` negative gate without another order.
- Express the illustrative strategy stop as 100 reviewed symbol ticks through the resolved
  `SymbolSpecification`, preserving EURUSD/GBPUSD `0.00100` stops while using `0.100` for USDJPY.
- Validate MQL5 broker-side SL/TP direction and stops/freeze distance against Bid for BUY and Ask
  for SELL on both initial and final ticks while retaining Ask/BUY and Bid/SELL market request price.
- Permit `demo` startup only with explicit enablement, exact reviewed identity/limits, a 32+
  character environment-owned secret, and loopback binding; continue rejecting `live` startup.
- Require take profit in demo risk policy and use 0.01 lot / one position application limits.
- Scope the MQL5 forbidden-trade scan so every component except the reviewed guard remains read-only
  and exactly one production-code `OrderSend` call exists.

### Fixed

- Block the unsafe USDJPY one-tick stop found during disabled-EA preflight; no order was placed.
- Accept successful FIBO MQL5 `OrderCheck` semantics (`bool=true`, `GetLastError()=0`,
  `check.retcode=0`) while preserving trade-server retcode handling for `OrderSend`.
- Tolerate at most `1e-12` broker-price serialization residue in durable result matching while
  keeping volume/identity exact and rejecting a real one-tick mismatch.
- Serialize unsigned 64-bit MQL5 broker order/deal IDs without signed narrowing and remove the
  incompatible pre-1.0 Market version property while retaining the platform version as 0.5.0.
- Validate MetaEditor compilation using an exact zero-error/zero-warning result and a freshly
  generated non-empty EX5 artifact instead of assuming the successful process exit code is zero.

### Security

- Preserve fail-closed behavior for absent, malformed, stale, future, non-inverse, or ambiguous
  conversion inputs; exact-inverse derivation uses only caller-supplied data and never performs a
  broker/network lookup or cross-rate inference.
- Add independent Python and MQL5 live-account barriers, independent default-off kill switches, and
  constant-time Python token verification without logging headers, secrets, or account login.
- Treat unknown, failed, claimed, submitted, filled, and partial reconciliation as blocking; compare
  reported symbol/side/volume/price/SL/TP against the claimed intent and reject overfills/conflicts.
- Defer Windows infrastructure hardening explicitly; 0.5.0 is not production-ready and LIVE remains
  forbidden. The reviewed v0.5.0 DEMO execution, inverse-conversion, compile/hash, and negative-drift
  validation gates are complete; any future MQL5 change requires a fresh deploy/compile/hash gate.

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

- Set the package/API version to 0.4.0 while preserving deterministic 0.3 backtesting behavior,
  version-derived identities, and the paper-only execution boundary.
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
