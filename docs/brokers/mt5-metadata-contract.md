# MT5 Read-Only Metadata Contract

Schema `1.0` is an offline JSON interchange between an already authenticated MetaTrader 5 terminal
and the broker-independent Python validation boundary. Application version 0.4.0 and interchange
schema 1.0 are versioned independently. Every document must declare:

```json
{
  "schema_version": "1.0",
  "mode": "read_only_metadata_probe",
  "source_type": "mql5_metadata_probe"
}
```

The importer rejects missing or additional fields, duplicate JSON keys, unknown source or side
enums, non-string financial values, malformed/non-finite decimals, negative values where prohibited,
malformed timestamps, naive timestamps, inconsistent calculation results, and unsupported schema or
safety modes. Files are UTF-8 and limited to one megabyte. Decimal text is parsed directly to Python
`Decimal`; MT5 `double` values are never first routed through a Python float and are never silently
rounded or repaired.

## Topology

The complete required structure is:

- `acquired_at`: aware acquisition wall-clock instant, normalized to UTC by Python;
- `broker`: non-secret company and server descriptors;
- `terminal`: name/build/version, point-in-time connection flag, raw server-time text, and an
  optional explicitly known UTC offset;
- `account`: currency, trade-mode code, leverage, margin/position-mode code, point-in-time trade
  permissions, and an optional local SHA-256 pseudonym—not a raw login;
- `requested_symbols`: exact uppercase names without alias or suffix guessing;
- `symbols`: currencies, grids, tick values, contract/volume rules, quotes, modes/bitmasks,
  stop/freeze levels, calculation/swap modes, margin fields, and observation time;
- `profit_calculations`: optional deterministic read-only hypothetical calculations;
- `margin_calculations`: optional deterministic read-only hypothetical calculations.

The exact accepted field set is defined by `broker_validation/parser.py` and exercised by strict
contract tests. Financial fields are JSON strings. Integers, booleans, and enum/bitmask codes retain
their native JSON types. Known order, filling, and expiration bits normalize to explicit sets;
unknown bits are preserved separately and become blocking validation findings.

MT5 exposes `SYMBOL_CURRENCY_PROFIT`, not a generic independent quote-currency field. The probe
exports that currency as `quote_currency` for an FX candidate and also preserves it as
`profit_currency`. The current mapper accepts this only for supported FX calculation modes and only
when quote and profit currencies agree. Other instruments remain unsupported rather than inferred.

## Time semantics

`acquired_at`, symbol `observed_at`, and calculation `observed_at` must be aware. The importer accepts
an explicit offset and normalizes it to UTC. MT5 server time is exported as `server_time_raw`. When
the terminal does not authoritatively expose its UTC offset, `server_utc_offset_minutes` is `null`;
the raw server-local value is never relabelled as UTC.

## Static and dynamic classification

Contract content includes broker/server identity, terminal build/version, account calculation
configuration, currencies, digits/point/tick grid, contract size, volume rules, capability bitmasks,
stop/freeze levels, calculation/swap modes and rates, and initial/maintenance margin fields.

Dynamic content includes acquisition/observation times, terminal connection, account permission
flags, symbol trade mode, Bid/Ask/reported spread, tick-value observations, and hypothetical
calculation results. Tick values are retained and validated, but deliberately excluded from the
contract fingerprint because MT5 values can be account/quote dependent.

## Canonical identity

Canonical JSON uses sorted object keys, compact separators, normalized decimal strings, UTC `Z`
timestamps, stable enum values, and deterministic collection ordering. SHA-256 over the complete
canonical interchange document is the `snapshot_fingerprint`. SHA-256 over the documented contract
projection is the `contract_fingerprint`; acquisition time, quotes, spread, tick values, connection,
permissions, and calculation cases are excluded. A quote-only change therefore changes the full
fingerprint but not the contract fingerprint. Terminal build, contract size, tick size, volume step,
calculation mode, stop/freeze rules, or swap terms change the contract fingerprint.

Actual snapshots and reports belong in ignored `var/broker-snapshots/` and `var/broker-reports/`
directories or a controlled off-host evidence archive. A hash detects change only when compared to
a separately trusted expected value; it is not a digital signature.
