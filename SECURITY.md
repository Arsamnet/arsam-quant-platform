# Security Policy

## Supported version

Version 0.5.x supports only paper and the specifically guarded FIBOGroup DEMO environment. It must
never be used for a live or production account.

## Reporting

Report suspected vulnerabilities privately to the repository owner or the designated internal
security channel. Do not include credentials, account data, or exploit details in public issues.
Preserve logs and timestamps without copying secrets.

## Mandatory controls

- Bind FastAPI and PostgreSQL to loopback unless a reviewed architecture explicitly changes it.
- Default-deny Windows Firewall inbound traffic; prefer VPN/private access for RDP.
- Use a least-privilege service account, Microsoft Defender, controlled patching, encrypted backups,
  and tested restoration.
- Keep broker credentials on the customer trading node. Never place secrets in Git, logs, MQL5, CI,
  screenshots, prompts, or support tickets.
- Rotate API/HMAC keys, use environment/secret-store injection, and redact authorization data.
- Treat financial news and AI output as untrusted data. Neither can override policy or execute.
- Run locked dependency installation and `pip-audit`; review lock updates rather than auto-merging.
- Treat historical CSV as untrusted input: validate strict schema/UTC/order/finite decimals, never
  deserialize pickle, and never let a backtest access a broker, network, external AI, or live mode.
- Treat MT5 snapshot files as untrusted: enforce bounded strict schema/Decimal/UTC parsing, compare
  hashes against separately trusted values, reject stale/unknown evidence, and never archive raw
  account logins or credentials.
- Keep the MQL5 metadata probe read-only; the forbidden-API scan supplements but does not replace
  human review and actual MetaEditor compilation.
- Keep the demo API on `127.0.0.1`, require its environment-owned token, and never log headers.
- Keep both kill switches default-off. Never add a demo-account override or a second trade boundary.
- Treat claimed/unknown execution as unresolved; reconcile magic/comment broker state before any
  further order and never automatically retry a submission.

Windows account, Defender, firewall, service isolation, full ACL, database, backup, and production
monitoring hardening are deliberately deferred from 0.5.0. This is not production readiness.

See [threat-model.md](docs/security/threat-model.md),
[windows-server-hardening.md](docs/runbooks/windows-server-hardening.md), and
[incident-response.md](docs/runbooks/incident-response.md).
