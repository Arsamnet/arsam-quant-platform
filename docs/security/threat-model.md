# Threat Model

## Assets and trust boundaries

Assets include broker credentials, API/HMAC secrets, account state, strategy/configuration, risk
limits, audit history, code/update integrity, and availability of safe position management. Trust
boundaries exist at MT5/Python localhost HTTP, external data/AI providers, PostgreSQL, operator/RDP,
future control-plane links, backups, CI/dependencies, and software updates.

## Principal threats and controls

| Threat | Bootstrap controls | Residual/future work |
|---|---|---|
| Public API exposure | Loopback-only validation; firewall guidance | Service identity and mTLS if boundary changes |
| Forged/replayed intent | Optional raw-body HMAC; UUID/nonce uniqueness; expiry | Durable distributed replay store; key rotation |
| Unsafe/compromised AI | Strict schema; advisory-only; risk after AI | Provider isolation, budgets, red-team suite |
| Prompt injection from news | External text excluded from authority and bootstrap payload | Classifier sandbox and adversarial fixtures |
| Risk bypass | Deterministic fail-closed rules; immutable decision; no intent after rejection | Independent MQL5 validation and signed policy |
| Credential disclosure | `.env` ignored; secret types; constrained logs; no EA secrets | Windows secret store and rotation automation |
| Dependency/supply-chain compromise | `uv.lock`, minimal dependencies, CI audit, pinned action majors | Provenance/SBOM/signing and hash policy review |
| Database loss/tamper | Versioned migration and audit model | PostgreSQL roles, encryption, backups, append-only history |
| Host/RDP compromise | Hardening runbook, Defender, least privilege, VPN preference | Central monitoring and endpoint response |
| Availability failure | New trades fail closed | Independent safe management of open positions |
| Malformed/poisoned historical data | Strict CSV, UTC, OHLC, duplicate/order, finite-value validation | Signed/provenance-verified market datasets |
| Look-ahead or result tampering | Streaming information boundary; canonical SHA-256 identities | Independent artifact signing and external replication |

The largest bootstrap residual risk is that no real MT5 validator, PostgreSQL recovery path, market
data provenance, or broker reconciliation exists. Consequently broker demo/live execution is
forbidden.
