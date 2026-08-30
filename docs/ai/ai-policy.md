# AI Policy

AI is advisory, optional, and downstream of a deterministic candidate signal. It cannot select
credentials, account IDs, URLs, code, commands, unrestricted volume/risk, or direct order placement.
Risk and MQL5 can reject any advice.

The default adapter returns an explicit deterministic `disabled` assessment and makes no network
call. If AI is policy-required, disabled/unavailable/invalid output rejects. Even when optional, an
unexpected unavailable or invalid response rejects; only deliberately configured disabled state is
treated as no advice.

A future OpenAI client must take its API key/model only from environment or a secret store, request
strict structured output, validate the bounded response, enforce timeouts and budgets, and record
model/prompt/schema versions and latency without logging secret or untrusted full text. No bootstrap
test makes an OpenAI request. Backtests use no current AI output; historical AI decisions must be a
versioned immutable dataset or fixture.
