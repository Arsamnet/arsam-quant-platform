# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
uses Semantic Versioning during pre-production.

## [Unreleased]

### Added

- Broker-independent `SymbolSpecification` and a static paper metadata provider for EURUSD,
  GBPUSD, and USDJPY.
- Explicit directed currency-conversion inputs and deterministic account-currency risk calculation.
- Regression coverage for every manually validated runtime behavior and combined risk failures.
- ADRs for early symbol validation, relative daily loss, symbol metadata, currency conversion, and
  per-symbol spread policy.

### Changed

- Prepare package version 0.2.0 while leaving release notes under Unreleased.
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
