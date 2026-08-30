# Security Policy

## Supported version

Version 0.1.x receives security fixes during bootstrap. It is paper-only and must not be used for
real-money or broker-demo execution.

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

See [threat-model.md](docs/security/threat-model.md),
[windows-server-hardening.md](docs/runbooks/windows-server-hardening.md), and
[incident-response.md](docs/runbooks/incident-response.md).
