# Windows Server 2025 Bootstrap and Hardening Runbook

This runbook is the operational checklist for preparing an Arsam Quant Platform Windows trading
node from the first provider login through private Tailscale administration and SSH public-key
authentication.

It records the bootstrap sequence used for the first `fx01` node and is intended to be repeatable
for later nodes. It deliberately uses placeholders instead of public IP addresses, passwords,
Tailscale authentication URLs, account numbers, or other secrets.

> **Current checkpoint:** the first `fx01` node has completed the runbook through **Phase 7 — SSH
> public-key authentication**. The remaining hardening phases below are still required before MT5
> broker calibration or any future demo deployment.

## Safety invariants

- Keep the provider console/recovery path available until private administration has been tested.
- Do not close public RDP or SSH until Tailscale access works from a second independent session.
- Do not disable password authentication until SSH public-key authentication is independently
  verified.
- Do not disable the built-in `Administrator` account until a named replacement administrator has
  been created and tested through both SSH and RDP.
- Never commit or paste passwords, private SSH keys, Tailscale login URLs, broker credentials, or
  real account snapshots into the repository.
- FastAPI, PostgreSQL, Redis, and internal control-plane services must never be exposed directly to
  the public Internet.
- Version 0.4.0 remains read-only with respect to MT5. No broker order submission is part of this
  bootstrap procedure.

---

## Phase 0 — Provider handoff and first login

### Checklist

- [x] Windows Server instance is provisioned and reachable through the provider console/RDP path.
- [x] Hostname is `fx01`.
- [x] Initial `Administrator` credentials are available from the provider.
- [x] Provider credentials are not stored in Git or project documentation.
- [ ] Bootstrap password has been rotated after the named-administrator phase is complete.

### Procedure

Use the provider-supplied RDP or console path for the first login. Keep that session available as a
recovery path while remote command-line administration is established.

Open **PowerShell as Administrator** and confirm the machine identity:

```powershell
hostname
whoami
```

Expected shape:

```text
fx01
fx01\administrator
```

Do not start by closing firewall rules or disabling RDP. The first objective is to establish a safe
secondary administration path.

---

## Phase 1 — Enable and verify Windows OpenSSH Server

### Checklist

- [x] `sshd` exists on the server.
- [x] `sshd` is running.
- [x] `sshd` startup type is `Automatic`.
- [x] TCP/22 listens locally on IPv4 and IPv6.
- [x] Local TCP/22 connectivity succeeds.

### Procedure

Inspect the service:

```powershell
Get-Service sshd
```

Start it and make it persistent:

```powershell
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
```

Verify listening sockets:

```powershell
Get-NetTCPConnection -LocalPort 22 -State Listen |
    Select-Object LocalAddress,LocalPort,State
```

Expected entries include listeners equivalent to:

```text
0.0.0.0   22   Listen
::        22   Listen
```

Verify the local stack independently of the external network:

```powershell
Test-NetConnection 127.0.0.1 -Port 22
```

Required result:

```text
TcpTestSucceeded : True
```

---

## Phase 2 — Align the Windows Firewall SSH rule with the active network profile

### Why this was necessary on `fx01`

The pre-created OpenSSH firewall rule was enabled for the `Private` profile while the VPS network
interfaces were classified as `Public`. The service was healthy and listening, but the rule did not
apply to the active network profile.

### Checklist

- [x] Active Windows network profile was inspected.
- [x] VPS interfaces remained classified as `Public`; they were **not** changed to `Private` merely
  to make SSH work.
- [x] OpenSSH inbound rule was enabled for `Public,Private`.
- [x] Rule direction is inbound and action is allow.

### Procedure

Inspect the active profiles:

```powershell
Get-NetConnectionProfile
```

Inspect the OpenSSH rule:

```powershell
Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" |
    Select-Object Name,Enabled,Profile,Direction,Action
```

Enable the rule for the profiles required during bootstrap:

```powershell
Set-NetFirewallRule `
    -Name "OpenSSH-Server-In-TCP" `
    -Profile Public,Private
```

Re-check it:

```powershell
Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" |
    Select-Object Name,Enabled,Profile,Direction,Action
```

Expected shape:

```text
Enabled   : True
Profile   : Private, Public
Direction : Inbound
Action    : Allow
```

> This broad bootstrap rule is temporary. Later phases restrict administration to the private
> Tailscale path and remove unnecessary public exposure.

---

## Phase 3 — Diagnose external SSH reachability without weakening Windows security

### What happened on the first node

Local Windows tests showed `sshd` running, TCP/22 listening, and localhost connectivity succeeding.
However, direct SSH from the Mac over the ordinary Internet path timed out. The same public endpoint
became reachable when the Mac used an existing external VPN.

This demonstrated that the Windows SSH service itself was functioning and that the remaining issue
was in the upstream/network path rather than a reason to disable Windows Firewall.

### Checklist

- [x] Local `sshd` health was confirmed before changing network security.
- [x] Direct public-path SSH timeout was observed.
- [x] SSH succeeded when an alternate VPN route was used.
- [x] Windows Firewall was **not** disabled as a troubleshooting shortcut.
- [x] A private overlay-network administration path was selected instead of depending on public
  SSH reachability.

### Mac diagnostics

Use finite timeouts when testing external ports:

```bash
nc -vz -w 5 <PUBLIC_SERVER_IP> 22
nc -vz -w 5 <PUBLIC_SERVER_IP> 3389
```

Do not record the real public IP in this runbook or other repository files.

---

## Phase 4 — First SSH connection and host-key verification

### Checklist

- [x] First SSH connection was initiated from the Mac.
- [x] The ED25519 host-key fingerprint shown by the Mac was verified against the key stored on the
  Windows server before accepting it.
- [x] Server identity, hostname, user, and `winget` availability were confirmed after login.

### Verify the server fingerprint on Windows

Before typing `yes` on the first SSH connection, obtain the fingerprint from the server itself:

```powershell
ssh-keygen -lf C:\ProgramData\ssh\ssh_host_ed25519_key.pub -E sha256
```

On the Mac, initiate the connection using the temporary reachable path:

```bash
ssh Administrator@<PUBLIC_SERVER_IP>
```

Only accept the host key if the displayed SHA-256 fingerprint exactly matches the fingerprint read
from Windows.

After login, verify the session:

```cmd
hostname
whoami
winget --version
```

The first node reported:

```text
hostname -> fx01
whoami   -> fx01\administrator
```

The exact `winget` version is not pinned by this runbook; record it in deployment evidence if it is
material to an installation issue.

---

## Phase 5 — Install Tailscale using the working WinGet source

### Why the source is explicit

On the first node, `winget` attempted to search the `msstore` source and returned a certificate
validation error. The Tailscale package was still available from the normal `winget` source. Rather
than weakening TLS or changing certificate policy, installation was explicitly scoped to that
working source.

### Checklist

- [x] Tailscale installed successfully.
- [x] Installation package hash was verified by WinGet.
- [x] Tailscale service/CLI is available.
- [x] Node was authenticated into the intended Tailnet.
- [x] Node hostname in Tailscale is `fx01`.
- [x] Server and Mac appear in the same Tailnet.

### Install

From the SSH or administrative terminal:

```cmd
winget install --id Tailscale.Tailscale -e --source winget --accept-source-agreements --accept-package-agreements
```

Verify the installed client:

```cmd
"C:\Program Files\Tailscale\tailscale.exe" version
```

Check initial state:

```cmd
"C:\Program Files\Tailscale\tailscale.exe" status
"C:\Program Files\Tailscale\tailscale.exe" ip -4
```

A newly installed node is expected to report `Logged out` / `NeedsLogin` until authenticated.

### Authenticate as an unattended server node

```cmd
"C:\Program Files\Tailscale\tailscale.exe" login --hostname=fx01 --unattended
```

The command prints a short-lived authentication URL. Open it in a trusted browser, authenticate to
the intended Tailnet, and **do not record that URL in Git, chat logs, tickets, or runbooks**.

After authentication:

```cmd
"C:\Program Files\Tailscale\tailscale.exe" status
"C:\Program Files\Tailscale\tailscale.exe" ip -4
```

Record the assigned private address in the operator's secure deployment notes, not in source
control. Tailscale addresses may change between environments, so all examples below use
`<TAILSCALE_SERVER_IP>`.

---

## Phase 6 — Prove private SSH access before touching public firewall rules

### Checklist

- [x] Mac and `fx01` are connected to the same Tailnet.
- [x] SSH to the Tailscale address succeeds.
- [x] Tailscale SSH path succeeds from a **new terminal session** while the existing recovery
  session remains open.
- [x] Existing external VPN on the Mac was disabled.
- [x] SSH over Tailscale continued to work without that VPN.
- [x] Public TCP/22 and TCP/3389 were **not** closed before this proof was complete.

### Procedure on the Mac

Optional reachability check:

```bash
ping -c 3 <TAILSCALE_SERVER_IP>
```

Open a new SSH session:

```bash
ssh Administrator@<TAILSCALE_SERVER_IP>
```

Inside that new session:

```cmd
hostname
whoami
```

Expected:

```text
fx01
fx01\administrator
```

Then disable any unrelated external VPN on the Mac and repeat:

```bash
ssh Administrator@<TAILSCALE_SERVER_IP>
```

Only after this succeeds is the private administration path considered established.

---

## Phase 7 — Configure and prove SSH public-key authentication

### Checklist

- [x] Mac has an ED25519 SSH key pair.
- [x] Only the `.pub` file was copied to the server.
- [x] Administrator public key was stored in
  `C:\ProgramData\ssh\administrators_authorized_keys`.
- [x] Inherited ACLs were removed from that file.
- [x] Full control is limited to local Administrators and SYSTEM.
- [x] `sshd` was restarted.
- [x] A second SSH session proved public-key-only authentication with password fallback disabled on
  the client side.
- [ ] Server-side password authentication is disabled later, after named administrator and recovery
  procedures are validated.

### 7.1 Check or create the Mac key

On the Mac:

```bash
ls -l ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub
```

If the pair does not exist:

```bash
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/id_ed25519
```

Use a passphrase for the private key unless an explicitly reviewed automation scenario requires a
different design.

Never copy or upload `~/.ssh/id_ed25519`.

### 7.2 Copy only the public key through Tailscale

```bash
scp ~/.ssh/id_ed25519.pub \
  Administrator@<TAILSCALE_SERVER_IP>:C:/Users/Administrator/id_ed25519.pub
```

### 7.3 Install the key for Windows administrators

Inside the Windows SSH session, enter PowerShell if necessary:

```cmd
powershell
```

Write the authorized-keys file:

```powershell
Get-Content "$env:USERPROFILE\id_ed25519.pub" |
    Set-Content -Encoding ascii "C:\ProgramData\ssh\administrators_authorized_keys"
```

Remove inherited ACLs:

```powershell
icacls.exe "C:\ProgramData\ssh\administrators_authorized_keys" /inheritance:r
```

Grant only the built-in Administrators group and SYSTEM using language-independent SIDs:

```powershell
icacls.exe "C:\ProgramData\ssh\administrators_authorized_keys" `
    /grant "*S-1-5-32-544:F" `
    /grant "*S-1-5-18:F"
```

Verify:

```powershell
icacls.exe "C:\ProgramData\ssh\administrators_authorized_keys"
```

Restart SSH:

```powershell
Restart-Service sshd
```

### 7.4 Prove key-only login from a second Mac terminal

Do **not** close the working administrative session before this succeeds.

```bash
ssh \
  -o PreferredAuthentications=publickey \
  -o PasswordAuthentication=no \
  Administrator@<TAILSCALE_SERVER_IP>
```

A key passphrase prompt is acceptable. A Windows account-password prompt is not.

Inside the new session:

```cmd
hostname
whoami
```

Required result:

```text
fx01
fx01\administrator
```

At this point the first-node bootstrap checkpoint is complete.

---

# Current bootstrap checkpoint

The following controls have been completed on the first `fx01` node:

- [x] Provider console/RDP recovery path established.
- [x] OpenSSH enabled, started, and made automatic.
- [x] TCP/22 local listener verified.
- [x] Windows Firewall profile mismatch diagnosed without disabling firewall protection.
- [x] First SSH host key independently verified.
- [x] Remote command-line administration proven.
- [x] Tailscale installed using the explicit `winget` source.
- [x] `fx01` and the administration Mac joined to the same Tailnet.
- [x] SSH over Tailscale proven without dependence on the Mac's previous VPN path.
- [x] Administrator ED25519 key authentication configured with restricted Windows ACLs.
- [x] Client-enforced key-only SSH test succeeded.

The server is **not yet considered fully hardened or deployment-ready**. Continue with the phases
below before installing or calibrating the broker runtime.

---

## Phase 8 — Create and prove a named administration account

### Required before disabling built-in Administrator

- [ ] Create a named local administrator for human operations.
- [ ] Give that account a unique strong password stored outside Git.
- [ ] Configure SSH public-key authentication for the named administrator.
- [ ] Prove SSH over Tailscale from a second terminal.
- [ ] Prove RDP over Tailscale.
- [ ] Confirm elevation works where required.
- [ ] Retain the provider console as break-glass recovery.
- [ ] Only then consider reducing or disabling routine use of the built-in `Administrator` account.

Do not create application/service processes under the human administrator account.

---

## Phase 9 — Move SSH and RDP administration to Tailscale-only access

### Preconditions

- [ ] Tailscale starts automatically after reboot.
- [ ] Named administrator works over Tailscale SSH.
- [ ] RDP works using the Tailscale address/private path.
- [ ] Provider console/recovery remains available.

### Required controls

- [ ] Restrict or remove public inbound TCP/22.
- [ ] Restrict or remove public inbound TCP/3389.
- [ ] Re-test SSH through Tailscale after every firewall change.
- [ ] Re-test RDP through Tailscale after every firewall change.
- [ ] Do not expose WinRM publicly.
- [ ] Confirm no new administrative listener became public as a side effect.

Prefer deleting temporary broad allow rules after the private path is proven rather than leaving
unused bootstrap exceptions behind.

---

## Phase 10 — Harden OpenSSH authentication

After the named administrator and Tailscale path have survived an independent reconnect/reboot test:

- [ ] Confirm all required administrators have working public keys.
- [ ] Preserve an out-of-band recovery path.
- [ ] Disable SSH password authentication.
- [ ] Disable empty passwords.
- [ ] Keep public-key authentication enabled.
- [ ] Review permitted administrative users/groups.
- [ ] Restart `sshd` and test a fresh key-only session before closing the previous one.
- [ ] Verify failed password attempts can no longer authenticate.

Never make authentication changes in the only remaining administrative session.

---

## Phase 11 — Windows platform security baseline

Before broker calibration:

- [ ] Install pending Windows security updates in a controlled maintenance/reboot window.
- [ ] Record Windows edition, build, and update state.
- [ ] Verify Microsoft Defender real-time protection.
- [ ] Verify behavior monitoring, antispyware, IOAV protection, and current signatures.
- [ ] Review tamper/cloud-protection settings as supported by the server edition.
- [ ] Review Windows Firewall profiles and inbound defaults.
- [ ] Enumerate all listening TCP ports and map each listener to an owning process.
- [ ] Remove or disable unnecessary services and legacy protocols.
- [ ] Configure time synchronization and record timezone/time-source assumptions.
- [ ] Configure event/audit logging and protected retention.
- [ ] Configure account lockout and sensible interactive-logon policy.
- [ ] Rotate provider/bootstrap credentials after recovery access is confirmed.

Useful inspection commands:

```powershell
Get-ComputerInfo |
    Select-Object WindowsProductName,WindowsVersion,OsBuildNumber,OsArchitecture

Get-TimeZone

Get-NetFirewallProfile |
    Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction

Get-MpComputerStatus |
    Select-Object AntivirusEnabled,AntispywareEnabled,RealTimeProtectionEnabled,
        BehaviorMonitorEnabled,IoavProtectionEnabled,AntivirusSignatureLastUpdated

Get-NetTCPConnection -State Listen |
    Sort-Object LocalPort |
    Select-Object LocalAddress,LocalPort,OwningProcess
```

Any unexpected listener, disabled security protection, failed time synchronization, or residual
public administrative exposure blocks broker calibration and deployment progression.

---

## Phase 12 — Application/service account and runtime isolation

Before running persistent Arsam Quant Platform components:

- [ ] Create dedicated least-privilege non-admin service identities.
- [ ] Use separate application/data/log directories with explicit ACLs.
- [ ] Deny interactive login to service identities where practical.
- [ ] Keep broker passwords, OpenAI keys, database credentials, and control-plane secrets out of
  source code and Git.
- [ ] Bind FastAPI to loopback/private interfaces only.
- [ ] Bind PostgreSQL and Redis to loopback/private interfaces only if/when installed.
- [ ] Verify from another host that internal service ports are not publicly reachable.
- [ ] Do not use Docker Desktop as a production dependency.

---

## Phase 13 — Development/runtime toolchain

After the Windows security baseline is complete:

- [ ] Install/verify Git.
- [ ] Install project-supported Python (3.12 baseline unless repository constraints change).
- [ ] Install/verify `uv`.
- [ ] Clone `Arsamnet/arsam-quant-platform` through an approved GitHub authentication method.
- [ ] Check out the reviewed milestone branch/commit before broker work.
- [ ] Run the Windows-compatible project quality/bootstrap checks.
- [ ] Do not copy `.env` or secrets from the development Mac wholesale.

For the current 0.4.0 validation milestone, the reviewed branch checkpoint before Windows-specific
validation was:

```text
feat/mt5-broker-validation
4238464  feat: add read-only MT5 broker validation
```

If the branch advances, record and review the exact newer commit rather than assuming this SHA is
still current.

---

## Phase 14 — MT5/FIBOGroup read-only calibration gate

Only after the preceding security phases are complete:

- [ ] Install the intended FIBOGroup MT5 terminal from an authenticated source.
- [ ] Use the intended **demo hedging** account; do not use live credentials.
- [ ] Open `ReadOnlyMetadataProbe.mq5` in MetaEditor.
- [ ] Compile independently and require `0 errors, 0 warnings` or explicitly review every warning.
- [ ] Run the probe only after source review confirms no trading/mutation API.
- [ ] Capture actual broker metadata for the explicitly reviewed symbols.
- [ ] Keep raw real broker snapshots out of Git.
- [ ] Run `fx-mt5-import` and `fx-broker-validate` offline.
- [ ] Reconcile `OrderCalcProfit` evidence for EURUSD and GBPUSD.
- [ ] For USDJPY/USD account calibration, require explicit directed currency-conversion evidence;
  never claim P/L equivalence without it.
- [ ] Archive fingerprints, terminal build, code commit, validation report, and operator evidence.
- [ ] Keep version 0.4.0 read-only; no `OrderSend` path is permitted.

Do not merge/tag/release v0.4.0 merely because the Python-side validation passed on macOS. The
Windows MetaEditor compilation and real broker read-only evidence remain release gates.

---

## Final deployment gate

A future demo deployment is blocked by any of the following:

- public SSH or RDP still exposed without an explicit approved exception;
- no tested Tailscale/private administration path;
- password-only SSH administration;
- unknown/unexpected listening ports;
- disabled Defender/firewall protection;
- failed or ambiguous time synchronization;
- secrets committed to Git or stored with broad ACLs;
- application services bound publicly;
- broker-calibration evidence missing or stale;
- MT5 probe not compiled/reviewed;
- any accidental demo/live order-execution capability introduced into milestone 0.4.0.

Treat unexpected infrastructure state as a fail-closed condition, not as permission to continue.