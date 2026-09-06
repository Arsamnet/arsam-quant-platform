# MT5 Read-Only Metadata Probe

`mt5/metadata_probe/ReadOnlyMetadataProbe.mq5` is a terminal-side script, not an Expert Advisor and
not an execution component. It runs inside the operator's already authenticated Windows MT5
terminal, reads `AccountInfo*`, `TerminalInfo*`, and `SymbolInfo*`, performs optional hypothetical
`OrderCalcProfit`/`OrderCalcMargin` calls, and writes schema-1.0 JSON to the terminal Files area.
Those calculation functions do not send an order.

The script has inputs for comma-separated requested symbols, output filename, and a small positive
hypothetical calibration volume. It never prompts for, reads, writes, hashes, or logs a password. It
does not persist the raw account login. Broker/server/company, account currency/modes/leverage,
terminal build/connection, and requested symbol facts are exported as audit evidence.

Operator procedure on a Windows validation node:

1. Review the exact source and its forbidden-API scan result.
2. Open it in MetaEditor and compile it independently.
3. Run it as a script on the intended already authenticated demo terminal.
4. Copy the output through an approved local/off-host evidence process.
5. Import with `fx-mt5-import`, record both fingerprints, and validate every intended symbol with an
   explicit UTC as-of.
6. Retain the raw/canonical snapshot, report, code version, terminal build, and human reconciliation.

The repository safety scan removes comments and string literals, then rejects lexical executable
uses of order-submission APIs, `CTrade`, Buy/Sell helpers, position opening/closing, and order
deletion/modification helpers. It is defense in depth, not a parser, compiler, control-flow proof, or
protection against indirect/dynamic invocation. Human source review and real MetaEditor compilation
remain mandatory.

The development host remains macOS, but the probe was independently compiled on the Windows
validation node in MetaEditor against FIBO Group MT5 build `6140` with `0 errors, 0 warnings`. It was
then run twice inside an already authenticated FIBOGroup demo terminal on 2026-09-06 and produced
the official distinct read-only schema-1.0 evidence pair. No order was submitted or modified.

The Python importer, validator, diff, fixtures, and safety tests still require neither Windows, the
MetaTrader5 Python package, a terminal, credentials, network access, nor broker access. No official
MetaTrader5 package was added to the project dependency graph.
