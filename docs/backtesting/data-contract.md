# Historical Data Contract

## Canonical bar

Schema `1.0` uses UTF-8 CSV with this exact header and no extra or missing fields:

```csv
timestamp,symbol,timeframe,bid_open,bid_high,bid_low,bid_close,spread
```

`timestamp` is the bar-open instant. The bar close is `timestamp + timeframe duration`. Supported
fixed timeframes are `M1`, `M5`, `M15`, `H1`, and `D1`. Input timestamps must be timezone-aware;
the loader explicitly normalizes aware offsets to UTC, while domain bars accept UTC only.

Prices and spread parse directly to `Decimal`. The data contains Bid OHLC plus one explicit
non-negative spread fixed throughout the bar:

```text
Ask OHLC = Bid OHLC + spread
midpoint = Bid + spread / 2
```

This assumption is deliberately visible and fingerprinted; spread is never implicitly zero. A
future explicit Bid/Ask or tick schema requires a new schema/model version.

## Validation

The loader rejects empty datasets, wrong headers or row shapes, empty values, malformed or non-finite
decimals, non-positive Bid prices, negative spread, invalid OHLC relationships, lowercase/empty
symbols, unsupported timeframes, naive timestamps, reverse chronology, duplicate
`(symbol, timeframe, timestamp)` identities, and mixed timeframes. Rows are never silently sorted or
financial values repaired.

## Metadata and checksum

Every immutable dataset records:

- dataset ID, schema version, dataset version, and declared source;
- sorted symbols and one timeframe;
- UTC start/end, event count, and `timezone = UTC`;
- lowercase SHA-256 of canonical schema-and-bar content.

Canonical decimals remove representational trailing zeros, timestamps use UTC `Z`, mappings are
key-sorted, and row order is preserved. Filesystem location, dataset label, version label, and source
label are not part of the content checksum, so the same logical bars have the same checksum anywhere.
They remain part of run metadata for provenance.

The committed `tests/fixtures/backtesting/eurusd_sample.csv` is synthetic, human-readable, and not
broker data. It contains six UTC M1 bars that exercise warm-up/no signal, signal creation, next-open
fill, transaction costs, and an intentionally ambiguous SL/TP bar resolved adversely.
