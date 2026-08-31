# Domain Glossary

- **MarketSnapshot:** immutable point-in-time Bid/Ask and previous-close observation.
- **AccountSnapshot:** point-in-time balance, equity, daily realized P/L, and position count.
- **SignalCandidate:** non-executable strategy proposal tied to one market snapshot and version.
- **StrategyDecision:** candidate or explicit no-signal result.
- **AiAssessment:** validated bounded advice with explicit available/disabled/unavailable/invalid
  status; never an order.
- **RiskDecision:** immutable deterministic approval/rejection and machine-readable reasons.
- **ExecutionIntent:** short-lived paper-only instruction created only after risk approval.
- **ExecutionResult:** idempotent paper adapter outcome.
- **EconomicEvent:** versioned point-in-time scheduled release with impact and affected currencies.
- **TradingNode:** isolated local runtime associated with a node identity and future broker account.
- **ControlPlane:** future SaaS coordination system with no direct broker credentials or OrderSend.
- **HistoricalBar:** immutable UTC Bid OHLC plus explicit fixed spread for one supported timeframe.
- **BacktestClock:** monotonic logical UTC time advanced only by historical events.
- **SimulatedPosition:** reproducible paper position filled by the no-network backtest broker.
- **TradeRecord:** immutable closed-trade ledger with gross P/L and separated costs.
- **BacktestResult:** canonical run identity, report, ledger, open positions, and audit sequence.
