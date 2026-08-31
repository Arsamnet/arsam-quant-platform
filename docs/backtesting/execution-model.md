# Backtest Execution Model

## Timing and quotes

A signal evaluated after bar N closes is queued for the next available bar open N+1. BUY entry uses
Ask open; SELL entry uses Bid open. Adverse deterministic slippage is then applied in configured
symbol ticks:

```text
BUY entry  = Ask open + slippage
SELL entry = Bid open - slippage
```

The candidate's close quote remains `requested_entry_price`; the next-open result is
`executed_entry_price`. This makes gaps auditable. Fill-time spread is checked again against the
symbol specification. Expiry, an unavailable spread policy, an excessive spread, a non-positive
fill, or a stop/target invalidated by the gap rejects the simulated entry.

## Stops, targets, and ambiguity

Long SL/TP triggers use Bid low/high because a long exits by selling at Bid. Short triggers use Ask
high/low because a short exits by buying at Ask. If both levels occur in one OHLC bar, stop loss wins.
For an adverse gap through a stop, the exit baseline is the worse open. A favorable TP gap receives
no improvement beyond the target. Exit slippage is adverse:

```text
BUY exit  = Bid baseline - slippage
SELL exit = Ask baseline + slippage
```

## P/L and costs

The ledger separates frictionless midpoint P/L from every modeled cost. For direction `+1` BUY or
`-1` SELL:

```text
gross quote P/L = direction * (reference exit - reference entry)
                  * contract_size * volume

spread cost = entry half-spread cost + exit half-spread cost
slippage cost = entry adverse distance + exit adverse distance
commission = commission_per_lot_per_side * volume * 2
net P/L = gross P/L - spread cost - slippage cost - commission - swap cost
```

Price-distance costs multiply the required `SymbolSpecification.contract_size` and volume. Quote
currency amounts convert only through an explicit fresh directed `CurrencyConversionRate`; the
engine never infers an inverse or cross. Commission is already in account currency. Swap is not
modeled and is explicitly recorded as zero/unsupported.

The static symbol specifications, spread, commission, slippage, and fills are engineering fixtures,
not FIBOGroup, MT5, or any broker calibration. Partial fills, order-book depth, latency distributions,
dynamic spread, swap, margin calls, limit orders, tick order, and broker calculation modes are out of
scope.
