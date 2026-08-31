# Windows Server 2025 Bootstrap and Hardening Runbook

This runbook is the operational checklist for preparing an Arsam Quant Platform Windows trading
node from the first provider login through private Tailscale administration, named administration,
SSH public-key authentication, access-path resilience testing, and the remaining Windows hardening
work.

It records the bootstrap sequence used for the first `fx01` node and is intended to be repeatable
for later nodes. It deliberately uses placeholders instead of public IP addresses, Tailscale IPs,
passwords, authentication URLs, broker account numbers, or other secrets.

> **Current checkpoint:** the first `fx01` node has completed the access bootstrap through named
> administrator creation, Tailscale unattended mode, SSH key-only validation, RDP over Tailscale,
> OpenSSH anti-abuse hardening, Administrator-session independence testing, and a controlled Windows
> reboot with private SSH recovery. Public SSH/RDP are intentionally still retained as temporary
> recovery paths until the wider Windows security baseline and all access tests are complete.

## Safety invariants

- Keep the provider console/recovery path available until private administration has been fully
  tested through logout, reconnect, and reboot.
- Do not close public RDP or SSH merely because Tailscale works once. Restrict them only after all
  replacement paths have been independently validated and survived reboot.
- Do not disable SSH password authentication until every required administrator has a verified key,
  an out-of-band recovery path exists, and key-only access has survived reboot.
- Do not disable the built-in `Administrator` account until a named replacement administrator has
  been created and tested through both SSH and RDP, elevation works, and recovery procedures are
  proven.
- Never commit or paste passwords, private SSH keys, Tailscale login URLs, broker credentials, real
  account snapshots, or provider secrets into the repository.
- FastAPI, PostgreSQL, Redis, and internal control-plane services must never be exposed directly to
  the public Internet.
- Windows Firewall must not be disabled as a troubleshooting shortcut.
- Infrastructure uncertainty is fail-closed: unexpected listener, route, service state, or access
  behavior blocks progression until explained.
- Version 0.4.0 remains read-only with respect to MT5. No broker order submission is part of this
  bootstrap procedure.

---

## Phase 0 — Provider handoff and first login

### Checklist

- [x] Windows Server instance is provisioned and reachable through the provider console/RDP path.
- [x] Hostname is `fx01`.
- [x] Initial `Administrator` credentials are available from the provider.
- [x] Provider credentials are not stored in Git or project documentation.
- [ ] Bootstrap/provider password rotation is deferred until all recovery-path tests are complete.

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

The pre-created OpenSSH firewall rule was enabled for the `Private` profile while the VPS Internet
interfaces were classified as `Public`. The service was healthy and listening, but the rule did not
apply to the active public network profile.

### Checklist

- [x] Active Windows network profiles were inspected.
- [x] VPS Internet interfaces remained classified as `Public`; they were **not** changed to
  `Private` merely to make SSH work.
- [x] OpenSSH inbound rule was enabled for `Public,Private` during bootstrap.
- [x] Rule direction is inbound and action is allow.
- [x] Tailscale interface later appeared as `Private`.

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

Later verification on `fx01` also confirmed:

```powershell
Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" |
    Get-NetFirewallAddressFilter

Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" |
    Get-NetFirewallPortFilter
```

with effective values equivalent to:

```text
LocalAddress  : Any
RemoteAddress : Any
Protocol      : TCP
LocalPort     : 22
```

> This broad bootstrap rule is temporary. It is intentionally retained until the remaining access
> and recovery tests are complete. Later phases restrict administration to the private Tailscale
> path and remove unnecessary public exposure.

---

## Phase 3 — Diagnose external SSH reachability without weakening Windows security

### What happened on the first node

Local Windows tests showed `sshd` running, TCP/22 listening, and localhost connectivity succeeding.
However, direct SSH from the Mac over the ordinary Internet path initially timed out. The same
public endpoint became reachable when the Mac used an existing external VPN.

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
- [x] Tailscale assigned the server a private 100.x address.

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

### Authenticate the node

```cmd
"C:\Program Files\Tailscale\tailscale.exe" login --hostname=fx01 --unattended
```

The command prints a short-lived authentication URL. Open it in a trusted browser, authenticate to
the intended Tailnet, and **do not record that URL in Git, tickets, deployment docs, or runbooks**.

After authentication:

```cmd
"C:\Program Files\Tailscale\tailscale.exe" status
"C:\Program Files\Tailscale\tailscale.exe" ip -4
```

Record the assigned private address in the operator's secure deployment notes, not in source
control. Tailscale addresses may vary between environments, so all examples below use
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
- [x] TCP/22 and TCP/3389 were reachable over the Tailscale path.
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
- [ ] Server-side password authentication remains enabled until the final access-hardening phase.

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
  -o IdentitiesOnly=yes \
  -i ~/.ssh/id_ed25519 \
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

---

## Phase 8 — Create and prove a named administration account

The named account is the intended human administration identity. The built-in `Administrator`
account remains available only as a temporary recovery/bootstrap path until later hardening.

### Completed checklist

- [x] Created local user `fxadmin`.
- [x] Used a strong, unique password and did not store it in Git.
- [x] Added `FX01\fxadmin` to the local `Administrators` group.
- [x] Corrected the account flag so `PasswordRequired=True`.
- [x] Verified the local Administrators SID `S-1-5-32-544` is enabled in the `fxadmin` token.
- [x] Verified `Get-LocalGroupMember -Group "Administrators"` contains both the built-in
  Administrator and `fxadmin`.
- [x] Proved public-key-only SSH over Tailscale as `fxadmin`.
- [x] Proved RDP over Tailscale as `FX01\fxadmin`.
- [x] Verified the RDP session name is `RDP-Tcp#...`.
- [x] Verified elevated administrative PowerShell works through UAC/`Run as administrator`.
- [x] Provider/public recovery paths remain intentionally available.
- [ ] Routine use of the built-in Administrator has not yet been disabled.

### Create the user

Read the password interactively instead of placing it on a command line:

```powershell
$Password = Read-Host "Enter NEW password for fxadmin" -AsSecureString
```

Create the account using a description of no more than the Windows local-user description limit:

```powershell
New-LocalUser `
    -Name "fxadmin" `
    -Password $Password `
    -FullName "Arsam Quant Administrator" `
    -Description "Arsam Quant admin"
```

If `InvalidPasswordException` is returned, do not weaken password policy. Re-enter a new strong
password and retry.

Add the account to local administrators:

```powershell
Add-LocalGroupMember `
    -Group "Administrators" `
    -Member "fxadmin"
```

Require a password for the account:

```powershell
net user fxadmin /passwordreq:yes
```

Verify:

```powershell
Get-LocalUser -Name "fxadmin" |
    Select-Object Name,Enabled,PasswordRequired,PasswordExpires

Get-LocalGroupMember -Group "Administrators" |
    Select-Object Name,ObjectClass
```

### Prove SSH as the named administrator

Windows OpenSSH uses `C:\ProgramData\ssh\administrators_authorized_keys` for members of the local
Administrators group, so the validated administrator key can be used for `fxadmin` without storing a
second copy in the user profile.

From the Mac:

```bash
ssh \
  -o IdentitiesOnly=yes \
  -i ~/.ssh/id_ed25519 \
  -o PreferredAuthentications=publickey \
  -o PasswordAuthentication=no \
  fxadmin@<TAILSCALE_SERVER_IP>
```

Verify:

```cmd
hostname
whoami
```

Expected:

```text
fx01
fx01\fxadmin
```

Confirm Administrators-group membership:

```powershell
whoami /groups | Select-String "S-1-5-32-544"
```

### Prove RDP over Tailscale

Use the Microsoft Windows App on macOS with:

```text
PC:       <TAILSCALE_SERVER_IP>
Username: FX01\fxadmin
Gateway:  none
```

On first connection, Windows App may warn that it cannot verify the RDP server certificate. Do not
blindly accept it. Compare the certificate SHA-1 fingerprint/thumbprint to the certificate on the
server:

```powershell
Get-ChildItem "Cert:\LocalMachine\Remote Desktop" |
    Format-List Subject,Issuer,Thumbprint,NotBefore,NotAfter
```

Only continue when the fingerprint shown by Windows App matches the server certificate.

Inside the RDP session verify:

```powershell
hostname
whoami
$env:SESSIONNAME
```

Expected shape:

```text
fx01
fx01\fxadmin
RDP-Tcp#...
```

`TermService` may show `StartType=Manual` while running because Remote Desktop Services can be
trigger-started. Do not change it merely to make the table say `Automatic`.

---

## Phase 9 — Tailscale unattended mode and multi-user behavior

### Completed checklist

- [x] Tailscale service is `Running` with `StartType=Automatic`.
- [x] Tailscale was explicitly put into unattended/daemon mode.
- [x] Existing non-default hostname was preserved while enabling unattended mode.
- [x] `tailscale debug prefs` confirmed `ForceDaemon=true`.
- [x] `WantRunning=true` and `LoggedOut=false` were confirmed.
- [x] Tailscale interface is present as a `Private` Windows network profile.
- [x] Tailscale traffic continued after logging out the built-in Administrator session.
- [x] TCP/22 and TCP/3389 remained reachable over the Tailnet after Administrator logout.
- [x] A Windows reboot later proved Tailscale returns before an interactive Administrator login.

### Enable unattended mode without resetting existing preferences

If `tailscale up --unattended` reports that all non-default flags must be repeated, **do not** use
`--reset` just to silence the message. Preserve the configured hostname explicitly:

```powershell
& "C:\Program Files\Tailscale\tailscale.exe" up --unattended --hostname=fx01
```

Validate effective preferences from the controlling administrative session:

```powershell
& "C:\Program Files\Tailscale\tailscale.exe" debug prefs
```

Required values include:

```text
"WantRunning": true
"LoggedOut": false
"Hostname": "fx01"
"ForceDaemon": true
```

### Important Windows multi-user CLI behavior

A secondary Windows user may see an error equivalent to:

```text
401 Unauthorized: Tailscale already in use by FX01\Administrator
```

when running `tailscale status` or `tailscale ip -4` while another Windows user owns the local
Tailscale control session. On `fx01`, this did **not** mean the network dataplane or the SYSTEM
service was down.

Do not treat this CLI ownership error as a connectivity failure when all of the following are true:

```text
ForceDaemon=true
Tailscale service=Running
Tailnet ping/TCP reachability succeeds
SSH/RDP over the Tailscale address succeeds
```

Inspect the service processes if needed:

```powershell
Get-Process Tailscale,tailscaled -IncludeUserName -ErrorAction SilentlyContinue |
    Select-Object Id,ProcessName,UserName,SessionId
```

The `tailscaled` service process should run under `NT AUTHORITY\SYSTEM`. More than one Tailscale
process can exist; do not kill them merely because multiple process rows are visible.

---

## Phase 10 — Prove independence from the built-in Administrator session

Before rebooting, prove that private administration does not depend on keeping the bootstrap
Administrator logged in.

### Completed checklist

- [x] `quser` showed the built-in Administrator and `fxadmin` as separate sessions.
- [x] `fxadmin` PowerShell was elevated via UAC when cross-session logout required elevation.
- [x] The built-in Administrator session was logged off while the `fxadmin` RDP session remained.
- [x] `sshd` remained `Running/Automatic` after Administrator logout.
- [x] Tailscale remained `Running/Automatic` after Administrator logout.
- [x] Local TCP/22 remained healthy.
- [x] Tailscale TCP/22 and TCP/3389 remained reachable from the Mac.

### Procedure

Inspect sessions:

```powershell
quser
```

If the Administrator session must be logged off from `fxadmin`, use an **elevated** PowerShell. A
non-elevated local administrator may receive `Error 5: Access is denied` because of UAC token
filtering.

Open an elevated shell:

```powershell
Start-Process powershell.exe -Verb RunAs
```

Then log off only the verified Administrator session ID:

```powershell
logoff <ADMINISTRATOR_SESSION_ID>
```

Never guess the session ID; read it from `quser` immediately before the command.

After logout, confirm service health:

```powershell
Get-Service sshd,Tailscale |
    Select-Object Name,Status,StartType

Test-NetConnection 127.0.0.1 -Port 22
```

From the Mac verify the private dataplane:

```bash
ping -c 3 <TAILSCALE_SERVER_IP>
nc -vz -w 5 <TAILSCALE_SERVER_IP> 22
nc -vz -w 5 <TAILSCALE_SERVER_IP> 3389
```

An initial SSH reconnect on the first node failed with `Exceeded MaxStartups`. Investigation proved
that this was **not** caused by Administrator logout or Tailscale failure; it was caused by public
SSH abuse described in the next phase.

---

## Phase 11 — OpenSSH abuse incident and anti-exhaustion hardening

### Incident observed during bootstrap

After Administrator logout, a new SSH connection from the Mac reached the Windows `sshd` process
but returned:

```text
kex_exchange_identification: banner line 0: Exceeded MaxStartups
```

The service itself was healthy:

```text
sshd      Running  Automatic
TCP/22    Listen on 0.0.0.0 and ::
localhost TCP/22 test succeeded
Tailscale TCP/22 test succeeded
```

Connection inspection showed a single external public source holding more than twenty simultaneous
SSH connections while the Mac had only the expected Tailnet connections. This exhausted the
unauthenticated startup pool under the default OpenSSH policy.

### Diagnosis commands

Count TCP/22 states:

```powershell
Get-NetTCPConnection -LocalPort 22 -ErrorAction SilentlyContinue |
    Group-Object State |
    Sort-Object Count -Descending |
    Select-Object Count,Name
```

Group connections by remote source:

```powershell
Get-NetTCPConnection -LocalPort 22 -ErrorAction SilentlyContinue |
    Where-Object {$_.State -ne "Listen"} |
    Group-Object RemoteAddress |
    Sort-Object Count -Descending |
    Select-Object Count,Name
```

Inspect effective SSH defaults:

```powershell
& "C:\Windows\System32\OpenSSH\sshd.exe" -T |
    Select-String "logingracetime|maxauthtries|maxstartups|persourcemaxstartups"
```

The first node initially reported:

```text
logingracetime 120
maxauthtries 6
maxstartups 10:30:100
persourcemaxstartups none
```

The absence of a per-source startup limit allowed one source to consume enough unauthenticated
slots to trigger random connection drops.

### Temporary block for the abusive source

A targeted Windows Firewall block was added for the observed abusive source without disabling the
firewall or closing all public SSH during the recovery-test phase:

```powershell
New-NetFirewallRule `
  -Name "Block-SSH-<ABUSIVE_IP>" `
  -DisplayName "Block abusive SSH source <ABUSIVE_IP>" `
  -Direction Inbound `
  -Action Block `
  -Protocol TCP `
  -LocalPort 22 `
  -RemoteAddress <ABUSIVE_IP> `
  -Profile Public,Private
```

Do not copy the first node's observed scanner IP into future deployments. Always inspect the actual
remote source before creating a targeted block.

Existing established connections can remain visible after adding a block rule. If a clean reset is
required and RDP/provider recovery is confirmed, restart the SSH service from the RDP session:

```powershell
Restart-Service sshd
```

If stale child processes remain after a controlled service stop, inspect before taking further
action. Do not indiscriminately kill system processes.

### Harden `sshd_config`

Back up the configuration before editing:

```powershell
Copy-Item `
  "C:\ProgramData\ssh\sshd_config" `
  "C:\ProgramData\ssh\sshd_config.pre-hardening.bak"
```

In the **global section before any `Match` block**, use:

```text
LoginGraceTime 30
MaxAuthTries 3
MaxStartups 10:30:100
PerSourceMaxStartups 4
```

Rationale:

- `LoginGraceTime 30` reduces the time an unauthenticated socket can occupy startup capacity.
- `MaxAuthTries 3` limits authentication attempts per connection.
- `MaxStartups 10:30:100` retains the standard global startup behavior.
- `PerSourceMaxStartups 4` prevents one source from consuming the entire unauthenticated pool.

Do **not** respond to this incident merely by greatly increasing `MaxStartups`; that increases the
resources an attacker can consume and does not solve the single-source exhaustion problem.

### Validate before restart

Syntax validation must return no output:

```powershell
& "C:\Windows\System32\OpenSSH\sshd.exe" -t
```

Inspect effective configuration:

```powershell
& "C:\Windows\System32\OpenSSH\sshd.exe" -T |
    Select-String "logingracetime|maxauthtries|maxstartups|persourcemaxstartups"
```

Required output:

```text
logingracetime 30
maxauthtries 3
maxstartups 10:30:100
persourcemaxstartups 4
```

Only after `sshd -t` succeeds:

```powershell
Restart-Service sshd
Get-Service sshd | Select-Object Name,Status,StartType
```

Then re-test key-only SSH from the Mac.

### Result on the first node

- [x] `Exceeded MaxStartups` root cause identified as public SSH connection abuse.
- [x] The observed abusive source was temporarily blocked.
- [x] `LoginGraceTime` reduced to 30 seconds.
- [x] `MaxAuthTries` reduced to 3.
- [x] `MaxStartups` retained at `10:30:100`.
- [x] `PerSourceMaxStartups` set to 4.
- [x] `sshd -t` passed with no output.
- [x] `sshd -T` confirmed all effective values.
- [x] `sshd` restarted and remained `Running/Automatic`.
- [x] Connection counts returned to expected low levels; occasional single external scanner
  connections no longer consumed the startup pool.
- [x] Named-admin key-only SSH over Tailscale succeeded after hardening.

The presence of occasional single public scanner connections is expected while public SSH remains
open. This is one reason public SSH remains a temporary recovery path rather than the intended
steady-state administration design.

---

## Phase 12 — Controlled reboot and access-path resilience

The reboot test proves that private administration does not depend on an interactive Administrator
session and that Tailscale/OpenSSH return automatically after Windows restart.

### Preconditions

- [x] Provider recovery console remains accessible.
- [x] Named administrator exists and has a proven SSH key.
- [x] RDP over Tailscale worked before reboot.
- [x] Tailscale `ForceDaemon=true` was confirmed.
- [x] `sshd` and Tailscale services were `Running/Automatic`.
- [x] OpenSSH configuration passed `sshd -t`.
- [x] Public recovery paths were intentionally left unchanged.

### Restart

Use a normal Windows restart from the elevated `fxadmin` RDP session:

```powershell
Restart-Computer
```

A provider hard-reset/power-cycle is **not** the preferred first resilience test because the goal is
to validate a normal operating-system reboot and service recovery path.

### Post-reboot checks from the Mac

Wait for the node to return, then test:

```bash
ping -c 3 <TAILSCALE_SERVER_IP>
nc -vz -w 5 <TAILSCALE_SERVER_IP> 22
nc -vz -w 5 <TAILSCALE_SERVER_IP> 3389
```

A small amount of packet loss or high latency during the first seconds after boot can occur while
Windows and the overlay network settle. Do not call the node healthy until TCP service checks and
actual authentication succeed.

Prove key-only SSH:

```bash
ssh \
  -o IdentitiesOnly=yes \
  -i ~/.ssh/id_ed25519 \
  -o PreferredAuthentications=publickey \
  -o PasswordAuthentication=no \
  fxadmin@<TAILSCALE_SERVER_IP>
```

Verify:

```cmd
hostname
whoami
powershell
```

Then:

```powershell
Get-Service sshd,Tailscale,TermService |
    Select-Object Name,Status,StartType

(Get-CimInstance Win32_OperatingSystem).LastBootUpTime

& "C:\Windows\System32\OpenSSH\sshd.exe" -T |
    Select-String "logingracetime|maxauthtries|maxstartups|persourcemaxstartups"
```

### First-node result

- [x] Tailscale private address responded again after reboot.
- [x] TCP/22 was reachable over Tailscale after reboot.
- [x] TCP/3389 was reachable over Tailscale after reboot.
- [x] Key-only SSH as `fxadmin` succeeded after reboot.
- [x] `hostname` returned `fx01`.
- [x] `whoami` returned `fx01\fxadmin`.
- [x] `sshd` returned as `Running/Automatic`.
- [x] Tailscale returned as `Running/Automatic`.
- [x] `TermService` was `Running` with trigger/manual start behavior unchanged.
- [x] OpenSSH anti-abuse settings persisted across reboot.
- [ ] A fresh interactive RDP login after this reboot should still be recorded explicitly before
  public RDP is restricted, even though TCP/3389 was reachable and RDP had already been proven
  before reboot.

---

# Current access-bootstrap checkpoint

The following controls have now been completed on the first `fx01` node:

- [x] Provider console/RDP recovery path retained.
- [x] OpenSSH enabled, started, automatic, and locally verified.
- [x] Windows Firewall remained enabled throughout troubleshooting.
- [x] First SSH host key independently verified.
- [x] Tailscale installed and server/Mac joined to the same Tailnet.
- [x] Tailscale unattended mode confirmed with `ForceDaemon=true`.
- [x] SSH over Tailscale works without the Mac's previous external VPN.
- [x] Administrator ED25519 key authentication configured with restricted ACLs.
- [x] Named administrator `fxadmin` created and added to Administrators.
- [x] `PasswordRequired=True` confirmed for `fxadmin`.
- [x] Public-key-only SSH as `fxadmin` proven.
- [x] RDP over Tailscale as `fxadmin` proven before reboot with certificate fingerprint validation.
- [x] Administrator session logout did not stop Tailscale or OpenSSH services.
- [x] Public SSH `MaxStartups` exhaustion incident diagnosed and contained.
- [x] Per-source SSH startup limiting enabled and validated.
- [x] Controlled Windows reboot completed.
- [x] Tailscale, TCP/22, TCP/3389, and key-only SSH returned after reboot.
- [x] OpenSSH hardening persisted across reboot.
- [ ] Fresh post-reboot RDP authentication remains to be explicitly recorded.
- [ ] Public SSH is intentionally still open as a temporary recovery path.
- [ ] Public RDP is intentionally still open as a temporary recovery path.
- [ ] SSH password authentication is intentionally still enabled during the remaining hardening
  work.
- [ ] Built-in `Administrator` is not yet disabled.

The server is **not yet considered fully hardened or deployment-ready**. Continue with the Windows
platform security baseline before broker calibration or MT5 validation.

---

## Phase 13 — Move SSH and RDP administration to Tailscale-only access

This phase is intentionally deferred until all security-baseline work, recovery checks, and the
fresh post-reboot RDP test are complete.

### Preconditions

- [x] Tailscale starts automatically after reboot.
- [x] Named administrator works over Tailscale SSH after reboot.
- [x] RDP worked using the Tailscale path before reboot.
- [x] Provider/public recovery remains available.
- [ ] Fresh post-reboot RDP login has been explicitly confirmed.
- [ ] Wider Windows security baseline is complete.

### Required controls

- [ ] Restrict or remove public inbound TCP/22.
- [ ] Restrict or remove public inbound TCP/3389.
- [ ] Re-test SSH through Tailscale after every firewall change.
- [ ] Re-test RDP through Tailscale after every firewall change.
- [ ] Do not expose WinRM publicly.
- [ ] Confirm no new administrative listener became public as a side effect.
- [ ] Remove obsolete temporary broad allow/block rules once the final policy is in place and tested.

Never remove the current access path until its replacement has been independently tested and has
survived reboot.

---

## Phase 14 — Harden OpenSSH authentication further

Per-source startup protection is already active, but password authentication is intentionally left
available during the remaining recovery-validation period.

After the named administrator, Tailscale path, provider recovery, and post-reboot RDP path have all
been fully revalidated:

- [x] `LoginGraceTime 30`.
- [x] `MaxAuthTries 3`.
- [x] `MaxStartups 10:30:100`.
- [x] `PerSourceMaxStartups 4`.
- [ ] Confirm all required administrators have working public keys.
- [ ] Preserve an out-of-band recovery path.
- [ ] Disable SSH password authentication.
- [ ] Disable empty passwords.
- [ ] Keep public-key authentication enabled.
- [ ] Review permitted administrative users/groups.
- [ ] Restart `sshd` and test a fresh key-only session before closing the previous one.
- [ ] Verify failed password attempts can no longer authenticate.
- [ ] Re-test after another maintenance reboot if authentication policy changes materially.

Never make authentication changes in the only remaining administrative session.

---

## Phase 15 — Windows platform security baseline

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
- [ ] Review the initial `net accounts` baseline; the first node initially reported weak/default
  values including no lockout threshold and no minimum password length.
- [ ] Set an approved password/lockout baseline only after ensuring it will not lock out recovery
  accounts unexpectedly.
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

net accounts
```

Any unexpected listener, disabled security protection, failed time synchronization, residual
unreviewed public administrative exposure, or account-policy regression blocks broker calibration
and deployment progression.

---

## Phase 16 — Application/service account and runtime isolation

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

## Phase 17 — Development/runtime toolchain

After the Windows security baseline is complete:

- [ ] Install/verify Git.
- [ ] Install project-supported Python (3.12 baseline unless repository constraints change).
- [ ] Install/verify `uv`.
- [ ] Clone `Arsamnet/arsam-quant-platform` through an approved GitHub authentication method.
- [ ] Check out the reviewed milestone branch/commit before broker work.
- [ ] Run the Windows-compatible project quality/bootstrap checks.
- [ ] Do not copy `.env` or secrets from the development Mac wholesale.

For the current 0.4.0 validation milestone, the reviewed implementation checkpoint before Windows-
specific validation was:

```text
feat/mt5-broker-validation
4238464  feat: add read-only MT5 broker validation
```

Documentation commits may advance the branch beyond that implementation SHA. Record and review the
exact current commit before broker validation rather than assuming this SHA remains the branch head.

---

## Phase 18 — MT5/FIBOGroup read-only calibration gate

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

- public SSH or RDP still exposed without an explicit approved temporary exception;
- no tested Tailscale/private administration path;
- private access has not survived logout/reboot testing;
- password-only SSH administration;
- no per-source protection against unauthenticated SSH startup exhaustion while public SSH remains
  temporarily exposed;
- unknown/unexpected listening ports;
- disabled Defender/firewall protection;
- failed or ambiguous time synchronization;
- secrets committed to Git or stored with broad ACLs;
- application services bound publicly;
- broker-calibration evidence missing or stale;
- MT5 probe not compiled/reviewed;
- any accidental demo/live order-execution capability introduced into milestone 0.4.0.

Treat unexpected infrastructure state as a fail-closed condition, not as permission to continue.