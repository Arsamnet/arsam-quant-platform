# Windows Server 2025 Bootstrap and Hardening Runbook

This runbook is the operational checklist for preparing an Arsam Quant Platform Windows trading
node from first provider access through private Tailscale administration, named administration,
OpenSSH hardening, Windows platform hardening, runtime isolation, and the read-only MT5 validation
gate.

It records the sequence validated on the first `fx01` node and is intended to be repeatable for
later nodes. It deliberately uses placeholders instead of public IP addresses, Tailscale IPs,
passwords, authentication URLs, broker account numbers, or other secrets.

> **Current checkpoint:** `fx01` is on Windows Server 2025 Standard build `26100.33296`; Windows
> security updates are current for the validated maintenance window; Defender and Windows Firewall
> are enabled; timezone is UTC; WinRM and Print Spooler are disabled; SMB1 and LLMNR are disabled;
> SMB signing is required; password, lockout, audit, and Security-log settings are hardened; public
> SSH/RDP firewall rules are disabled; SSH/RDP administration is permitted only through explicit
> Tailscale-interface rules; the provider console is a verified break-glass path; and a SYSTEM
> startup task has been proven to re-apply Tailscale adapter NetBIOS/file-sharing hardening after
> every reboot. Server-side SSH password authentication and the built-in `Administrator` account
> remain enabled pending the final access-hardening decision. MT5/broker validation has not started.

## Safety invariants

- Keep the provider console/recovery path available while changing networking, firewall, logon, or
  authentication controls.
- Never remove the current administration path until its replacement has been independently tested
  through a fresh connection and, where material, survived reboot.
- Never disable Windows Firewall as a troubleshooting shortcut.
- Do not weaken RDP NLA/TLS to diagnose connectivity.
- Do not delete CBS/Windows Update registry markers, `pending.xml`, WinSxS contents, or
  `SoftwareDistribution` as an ad-hoc update workaround.
- Do not disable the built-in `Administrator` account until the named administrator, Tailscale
  administration, and provider-console break-glass paths are all proven and documented.
- Do not disable SSH password authentication until every required administrator has a verified
  public key and an out-of-band recovery path exists.
- Never commit passwords, private SSH keys, Tailscale authentication URLs, broker credentials,
  provider secrets, or real account snapshots.
- FastAPI, PostgreSQL, Redis, and other internal control-plane services must never be exposed
  directly to the public Internet.
- Infrastructure uncertainty is fail-closed: unexpected listener, route, service state, update
  state, or access behavior blocks progression until explained.
- Version 0.4.0 remains read-only with respect to MT5. No broker order submission belongs in this
  milestone.

---

## Phase 0 — Provider handoff and first login

### Checklist

- [x] Windows Server instance provisioned and provider console/RDP path reachable.
- [x] Hostname is `fx01`.
- [x] Initial provider `Administrator` credentials were received securely.
- [x] Provider/bootstrap credentials are not stored in Git.
- [x] Provider console was later re-tested as an out-of-band break-glass path.
- [x] The provider-supplied/bootstrap `Administrator` password was rotated after recovery paths were
  proven.
- [x] Login through the provider console with the new `Administrator` password was proven.

Initial identity verification:

```powershell
hostname
whoami
```

Expected shape:

```text
fx01
fx01\administrator
```

Do not begin a fresh node by closing firewall rules or disabling RDP. Establish and verify a safe
secondary administration path first.

---

## Phase 1 — Enable and verify Windows OpenSSH Server

### Checklist

- [x] `sshd` exists.
- [x] `sshd` is running.
- [x] `sshd` startup type is `Automatic`.
- [x] TCP/22 listens locally on IPv4 and IPv6.
- [x] Local TCP/22 connectivity succeeds.

```powershell
Get-Service sshd
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
Get-NetTCPConnection -LocalPort 22 -State Listen
Test-NetConnection 127.0.0.1 -Port 22
```

---

## Phase 2 — Align the Windows Firewall SSH rule with the active profile during bootstrap

The first node's public VPS interfaces were correctly classified as `Public`; they were not changed
to `Private` simply to make SSH work. During bootstrap the built-in OpenSSH rule was temporarily
allowed for `Public,Private` while a private administration path was established.

### Bootstrap checklist

- [x] Active network profiles inspected.
- [x] Internet-facing interfaces remained `Public`.
- [x] Tailscale later appeared as `Private`.
- [x] `OpenSSH-Server-In-TCP` was temporarily enabled for `Public,Private` during bootstrap.
- [x] Windows Firewall remained enabled throughout troubleshooting.

Useful inspection:

```powershell
Get-NetConnectionProfile
Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" |
    Select-Object Name,Enabled,Profile,Direction,Action
```

The broad rule is no longer the steady-state policy; Phase 13 records the final Tailscale-only
management firewall state.

---

## Phase 3 — Diagnose external SSH reachability without weakening Windows security

On the first node, local `sshd` health and localhost TCP/22 succeeded while a direct public route
initially timed out. An alternate VPN route succeeded, proving the Windows SSH service was healthy
and that the remaining issue was upstream/network-path related. Windows Firewall was not disabled.

Finite external diagnostics from an operator workstation:

```bash
nc -vz -w 5 <PUBLIC_SERVER_IP> 22
nc -vz -w 5 <PUBLIC_SERVER_IP> 3389
```

Do not record the real public IP in this runbook.

---

## Phase 4 — First SSH connection and host-key verification

Before accepting a first SSH host key, compare the client-presented fingerprint to the server's
actual ED25519 host key:

```powershell
ssh-keygen -lf C:\ProgramData\ssh\ssh_host_ed25519_key.pub -E sha256
```

Only accept the first SSH connection when the fingerprints match.

---

## Phase 5 — Install and authenticate Tailscale

Tailscale was installed from the normal WinGet source after the `msstore` source produced a
certificate validation problem. TLS/certificate policy was not weakened.

```cmd
winget install --id Tailscale.Tailscale -e --source winget --accept-source-agreements --accept-package-agreements
```

Authenticate without recording the short-lived login URL:

```cmd
"C:\Program Files\Tailscale\tailscale.exe" login --hostname=fx01 --unattended
```

### Checklist

- [x] Tailscale installed.
- [x] Server and operator workstation joined to the intended Tailnet.
- [x] Tailscale hostname is `fx01`.
- [x] Private Tailscale address assigned.
- [x] Real Tailscale address is kept out of source control.

---

## Phase 6 — Prove private SSH/RDP reachability before restricting public access

### Checklist

- [x] SSH to `<TAILSCALE_SERVER_IP>` succeeded from a new terminal.
- [x] SSH continued to work with the workstation's unrelated external VPN disabled.
- [x] TCP/22 and TCP/3389 were reachable through Tailscale.
- [x] Public SSH/RDP were not restricted until the private path was proven.

```bash
ping -c 3 <TAILSCALE_SERVER_IP>
nc -vz -w 5 <TAILSCALE_SERVER_IP> 22
nc -vz -w 5 <TAILSCALE_SERVER_IP> 3389
```

---

## Phase 7 — Configure and prove SSH public-key authentication

The operator uses an ED25519 key. Only the public key is copied to Windows. For local
Administrators, Windows OpenSSH uses:

```text
C:\ProgramData\ssh\administrators_authorized_keys
```

The file ACL was hardened to built-in Administrators and SYSTEM using language-independent SIDs.

```powershell
icacls.exe "C:\ProgramData\ssh\administrators_authorized_keys" /inheritance:r
icacls.exe "C:\ProgramData\ssh\administrators_authorized_keys" /grant "*S-1-5-32-544:F" /grant "*S-1-5-18:F"
Restart-Service sshd
```

Prove key-only client behavior with password fallback disabled:

```bash
ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 \
  -o PreferredAuthentications=publickey \
  -o PasswordAuthentication=no \
  fxadmin@<TAILSCALE_SERVER_IP>
```

### Checklist

- [x] Administrator key authentication proven.
- [x] Named-admin key authentication proven.
- [x] Client-side key-only proof repeated after reboots.
- [ ] Server-side SSH password authentication remains enabled pending Phase 14.

---

## Phase 8 — Create and prove named administrator `fxadmin`

### Checklist

- [x] `fxadmin` created with a strong unique password.
- [x] `fxadmin` added to local Administrators.
- [x] `PasswordRequired=True` confirmed.
- [x] Administrators group contains only the intended built-in `Administrator` and `fxadmin` human
  administrator accounts.
- [x] Public-key-only SSH over Tailscale proven as `fxadmin`.
- [x] RDP over Tailscale proven as `FX01\fxadmin`.
- [x] Elevated PowerShell through UAC proven.
- [x] RDP server certificate fingerprint was checked on initial connection.
- [x] Provider console remains available as break-glass recovery.
- [ ] Built-in `Administrator` remains enabled pending the final access decision.

`TermService` may legitimately show `StartType=Manual` while running because it is trigger-started;
do not change it merely to obtain an `Automatic` label.

RDP security was verified as:

```text
UserAuthentication = 1   # NLA enabled
SecurityLayer      = 2   # TLS
MinEncryptionLevel = 2
```

Do not weaken these values for troubleshooting.

---

## Phase 9 — Tailscale unattended mode and Windows multi-user behavior

Tailscale was explicitly placed in unattended/daemon mode while preserving the hostname:

```powershell
& "C:\Program Files\Tailscale\tailscale.exe" up --unattended --hostname=fx01
& "C:\Program Files\Tailscale\tailscale.exe" debug prefs
```

Required proven preferences:

```text
WantRunning=true
LoggedOut=false
Hostname=fx01
ForceDaemon=true
```

The SYSTEM service is the connectivity authority. A secondary Windows user may receive a local
Tailscale CLI `401 Unauthorized` ownership message while the dataplane remains healthy. Treat that
as a local control-session ownership condition, not a network outage, when service state and actual
Tailnet reachability are healthy.

---

## Phase 10 — Prove independence from the built-in Administrator session

The built-in Administrator session was logged off while `fxadmin` remained active. Tailscale and
OpenSSH remained healthy and TCP/22 and TCP/3389 stayed reachable over the Tailnet.

### Checklist

- [x] `quser` used to identify sessions before cross-session logout.
- [x] Cross-session logout performed only from elevated PowerShell.
- [x] `sshd` remained `Running/Automatic`.
- [x] Tailscale remained `Running/Automatic`.
- [x] Private SSH/RDP reachability survived Administrator logout.

Never guess a session ID before `logoff`; read it from `quser` immediately before the action.

---

## Phase 11 — OpenSSH abuse incident and anti-exhaustion hardening

While public SSH was temporarily exposed during bootstrap, one abusive source consumed many
unauthenticated connections and triggered:

```text
Exceeded MaxStartups
```

This was diagnosed as public SSH connection abuse, not Tailscale or Administrator-session failure.
The source itself is intentionally not recorded in Git.

Initial effective values:

```text
LoginGraceTime 120
MaxAuthTries 6
MaxStartups 10:30:100
PerSourceMaxStartups none
```

Final global `sshd_config` hardening, before any `Match` block:

```text
LoginGraceTime 30
MaxAuthTries 3
MaxStartups 10:30:100
PerSourceMaxStartups 4
```

Validate before restart:

```powershell
& "C:\Windows\System32\OpenSSH\sshd.exe" -t
& "C:\Windows\System32\OpenSSH\sshd.exe" -T |
    Select-String "logingracetime|maxauthtries|maxstartups|persourcemaxstartups"
```

### Checklist

- [x] Root cause identified.
- [x] A targeted temporary firewall block was used for the observed abusive source during the
  bootstrap window.
- [x] `LoginGraceTime 30`.
- [x] `MaxAuthTries 3`.
- [x] `MaxStartups 10:30:100` retained.
- [x] `PerSourceMaxStartups 4`.
- [x] `sshd -t` passed.
- [x] Effective values verified with `sshd -T`.
- [x] Settings survived reboot.
- [ ] Remove any obsolete temporary scanner-specific block rule during final firewall housekeeping
  if it is still present and no longer needed.

Do not increase global `MaxStartups` merely to accommodate Internet scanners.

---

## Phase 12 — Controlled reboot, update servicing, and access-path resilience

Multiple normal Windows restarts were used to prove that private administration does not depend on
an interactive Administrator session and that Tailscale/OpenSSH recover automatically.

### Proven restart behavior

- [x] Tailscale returns automatically after reboot.
- [x] TCP/22 returns over Tailscale.
- [x] TCP/3389 returns over Tailscale.
- [x] Key-only SSH as `fxadmin` works after reboot.
- [x] Fresh RDP authentication as `FX01\fxadmin` works after reboot.
- [x] Provider console login works after reboot.
- [x] Provider console login with the rotated `Administrator` password works.
- [x] OpenSSH anti-abuse settings persist.

### RDP recovery incident observed during update servicing

During one update/reboot cycle, RDP was temporarily unavailable even though `TermService`, the
3389 listener, firewall state, and local/Tailscale TCP reachability appeared healthy. A controlled
`Restart-Service TermService -Force` attempt coincided with the current SSH session dropping. This
was an observed correlation, not a proven causal diagnosis. Immediately afterwards Tailscale,
TCP/22, and TCP/3389 remained reachable, SSH could reconnect, and RDP later recovered.

Operational lesson: before restarting a management service, keep at least two independently tested
management/recovery paths available. Do not assume a transient RDP symptom requires weakening NLA,
TLS, or Windows Firewall.

### Restart command

Prefer a normal OS restart:

```powershell
Restart-Computer
```

If Windows refuses because other users are logged on, inspect `quser` and sign out the extra session
cleanly rather than immediately forcing the restart.

---

# Current access/security checkpoint

- [x] Provider console break-glass path verified.
- [x] Bootstrap/default `Administrator` password rotated and new password login proven.
- [x] Named administrator `fxadmin` established and tested.
- [x] Tailscale unattended mode proven across reboots.
- [x] Public-key-only SSH as `fxadmin` proven across reboots.
- [x] RDP over Tailscale proven across reboots.
- [x] Public OpenSSH allow rule disabled.
- [x] Built-in broad Remote Desktop firewall rules disabled.
- [x] Explicit Tailscale-interface SSH/RDP rules enabled.
- [x] WinRM disabled.
- [x] Print Spooler disabled.
- [x] Windows platform update/hardening work below substantially completed.
- [x] Tailscale adapter startup hardening task proven manually and via real reboot.
- [ ] Server-side SSH password authentication still enabled.
- [ ] Built-in `Administrator` still enabled as break-glass account.
- [ ] Final remaining listener/service review and tamper/cloud-protection review still required
  before the Windows baseline is called fully complete.

The server is **not yet deployment-ready** and MT5/broker calibration must not start until the
remaining hardening gates are reviewed.

---

## Phase 13 — Move SSH and RDP administration to Tailscale-only firewall access

The public administration transition is complete at the Windows Firewall layer.

### Final management firewall rules

Explicit allow rules were created on the `Tailscale` interface and `Private` profile:

```text
ArsamQuant-Tailscale-SSH-TCP
ArsamQuant-Tailscale-RDP-TCP
ArsamQuant-Tailscale-RDP-UDP
```

Legacy/broad rules were then disabled only after fresh Tailscale connections succeeded:

```text
OpenSSH-Server-In-TCP                Enabled=False
RemoteDesktop-Shadow-In-TCP          Enabled=False
RemoteDesktop-UserMode-In-TCP        Enabled=False
RemoteDesktop-UserMode-In-UDP        Enabled=False
```

### Checklist

- [x] Tailscale SSH TCP/22 rule created and interface-scoped.
- [x] Tailscale RDP TCP/3389 rule created and interface-scoped.
- [x] Tailscale RDP UDP/3389 rule created and interface-scoped.
- [x] New key-only SSH connection proven after disabling the broad OpenSSH rule.
- [x] Fresh RDP connection proven after disabling broad Remote Desktop rules.
- [x] Provider console proven as independent recovery.
- [x] Public SSH Windows Firewall allow rule disabled.
- [x] Public/broad RDP Windows Firewall allow rules disabled.
- [x] Configuration survived reboot.
- [x] WinRM is not exposed as an alternate remote management listener.
- [ ] Final firewall housekeeping should remove any obsolete temporary scanner-specific block rule
  if still present.

Do not re-enable broad public SSH/RDP merely for convenience.

---

## Phase 14 — Harden OpenSSH authentication further

Per-source startup protection and Tailscale-only firewall access are active. The remaining SSH
policy decision is server-side password authentication.

### Current checklist

- [x] `LoginGraceTime 30`.
- [x] `MaxAuthTries 3`.
- [x] `MaxStartups 10:30:100`.
- [x] `PerSourceMaxStartups 4`.
- [x] Required administrator public-key authentication proven.
- [x] Out-of-band provider console recovery path proven.
- [ ] Disable SSH password authentication.
- [ ] Explicitly disable empty passwords if not already enforced by the effective config.
- [ ] Keep public-key authentication enabled.
- [ ] Review/limit permitted administrative users or groups if an allow-list is adopted.
- [ ] Restart `sshd` and test a fresh key-only session before closing the previous one.
- [ ] Re-test after a maintenance reboot if authentication policy changes materially.

Never make authentication changes in the only remaining administrative session.

---

## Phase 15 — Windows platform security baseline

### 15.1 Operating system and Windows Update servicing

Validated OS state:

```text
Windows Server 2025 Standard
Build 26100.33296
Timezone UTC
```

The initial update search found four software updates in the maintenance window, including Windows
Security platform, MSRT, .NET Framework security, and the cumulative Windows security update.
Windows Update COM search worked over SSH, but creating the downloader/installer from the remote SSH
session returned `0x80070005 E_ACCESSDENIED`. Do not weaken UAC/DCOM/ACLs to bypass this. Perform
Windows Update download/install from an interactive elevated RDP/provider-console session.

During the first install pass, the Windows Security platform update and MSRT succeeded while the
.NET and cumulative security updates reported `0x80240035` (`WU_E_UPDATE_NOT_PROCESSED`) in a
reboot-pending servicing state. The system was rebooted normally and servicing was allowed to
complete rather than deleting update state. Final validation proved:

- [x] `KB5120233` installed; build advanced to `26100.33296`.
- [x] `KB5120708` installed.
- [x] Pending software update count is zero for the validated maintenance window.
- [x] CBS reboot-pending flag is false.
- [x] Windows Update reboot-required flag is false.
- [x] Pending file-rename flag is false.

Component-store validation before forcing any repair showed:

```text
DISM /Online /Cleanup-Image /ScanHealth  -> no corruption
DISM /Online /Cleanup-Image /CheckHealth -> no corruption
sfc /verifyonly                          -> no integrity violations
```

Do not run destructive/reset-style update remediation when normal servicing/reboot resolves the
state.

### 15.2 Defender

Validated protections:

- [x] Antivirus enabled.
- [x] Antispyware enabled.
- [x] Real-time protection enabled.
- [x] Behavior monitoring enabled.
- [x] IOAV protection enabled.
- [x] Network Inspection System enabled.
- [x] Defender signatures current; `DefenderSignaturesOutOfDate=False`.
- [ ] Review tamper/cloud-protection settings as supported by the installed Server edition/policy.

### 15.3 Windows Firewall

Effective `netsh advfirewall show allprofiles` policy was verified for Domain, Private, and Public:

```text
State: ON
Policy: BlockInbound,AllowOutbound
```

Firewall drop logging was then enabled on all profiles while allowed-connection logging remains off:

```text
LogBlocked          True
LogAllowed          False
LogMaxSizeKilobytes 32767
```

- [x] Domain firewall enabled.
- [x] Private firewall enabled.
- [x] Public firewall enabled.
- [x] Effective inbound default is block.
- [x] Effective outbound default is allow.
- [x] Dropped-packet logging enabled.
- [x] Public SSH/RDP broad allow rules disabled.
- [x] Tailscale-interface management rules enabled.

### 15.4 Time synchronization

The server initially used a provider/default US timezone. Time synchronization itself was healthy
against the configured Windows time source. The system timezone was changed to UTC and NTP remained
healthy afterwards.

- [x] Time synchronization healthy.
- [x] Timezone set to UTC.
- [x] DST does not affect the server timezone.

### 15.5 WinRM and Print Spooler

Baseline inspection found WinRM running automatically with HTTP/5985 and HTTPS/5986 listeners on
all interfaces; an inbound HTTP rule was enabled even for the Public profile. The application does
not require WinRM, so the exposure was removed rather than merely relying on network obscurity.

Final state:

```text
WinRM   Stopped / Disabled
Spooler Stopped / Disabled
```

The Windows Remote Management firewall rules are disabled. Post-change listener verification showed
5985/5986 removed.

- [x] Public WinRM rule disabled first.
- [x] WinRM service stopped and disabled.
- [x] WinRM firewall rules disabled.
- [x] 5985/5986 listeners removed.
- [x] Print Spooler stopped and disabled.
- [x] SSH, Tailscale, and RDP remained healthy after these changes.

### 15.6 SMB, LLMNR, and NetBIOS

Validated SMB state:

```text
SMB1                         Disabled
SMB2/3                       Enabled
SMB server signing enabled   True
SMB server signing required  True
SMB client signing enabled   True
SMB client signing required  True
Insecure guest logons        False
```

No enabled `File and Printer Sharing` firewall rule was found during validation. Administrative
default shares may still exist locally; do not confuse share existence with public firewall
exposure.

LLMNR was explicitly disabled with policy value:

```text
HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient\EnableMulticast = 0
```

NetBIOS was explicitly disabled on the physical VirtIO interfaces. The Tailscale virtual adapter
behaved differently: after every reboot Tailscale recreated/re-enabled both `ms_server` and
`ms_msclient` bindings and returned `TcpipNetbiosOptions` to `0`, causing UDP/137, UDP/138, and
TCP/139 to listen on the Tailscale address.

Manual hardening proved the desired state:

```text
ms_tcpip             True
ms_tcpip6            True
ms_server            False
ms_msclient          False
TcpipNetbiosOptions  2
UDP/137               no listener
UDP/138               no listener
TCP/139               no listener
```

Because these values did not persist by themselves across reboot, the following local startup
control was created:

```text
Task:   ArsamQuant-Tailscale-Network-Hardening
Script: C:\ProgramData\ArsamQuant\Enforce-TailscaleNetworkHardening.ps1
Run as: SYSTEM / Highest
Trigger: AtStartup
```

The script waits for the Tailscale adapter to be `Up`, disables only `ms_server` and `ms_msclient`,
sets NetBIOS to `2`, and records its result in:

```text
C:\ProgramData\ArsamQuant\tailscale-network-hardening.log
```

It does **not** disable IPv4 or IPv6. The task was first executed manually under SYSTEM and returned
`LastTaskResult=0`. A subsequent real Windows reboot then proved the startup trigger also returned
`LastTaskResult=0` and the log showed:

```text
NetBIOS=2
ms_server=False
ms_msclient=False
UDP137138=0
TCP139=0
Task completed
```

- [x] SMB1 disabled.
- [x] SMB signing required on server and client.
- [x] Insecure guest logons disabled.
- [x] LLMNR disabled.
- [x] NetBIOS disabled on physical adapters.
- [x] Tailscale file-sharing/client bindings disabled by boot-time enforcement.
- [x] Tailscale NetBIOS disabled by boot-time enforcement.
- [x] No 137/138/139 listener remains after the startup hardening task runs.
- [x] Startup task proven manually under SYSTEM.
- [x] Startup task proven by a real reboot.

### 15.7 Password and account lockout policy

Initial local account policy was weak/default despite password complexity already being enabled:

```text
MinimumPasswordLength = 0
PasswordHistorySize   = 0
LockoutBadCount       = 0
PasswordComplexity    = 1
ClearTextPassword     = 0
```

Lockout was intentionally not enabled while public password-bearing administration paths were still
available, to avoid scanner-driven denial-of-service account lockouts. After public SSH/RDP firewall
access was removed and three independent recovery/management paths were proven, the final policy
was set to:

```text
Minimum password age      1 day
Maximum password age      42 days
Minimum password length   14
Password history           24
Lockout threshold          5
Lockout duration           15 minutes
Lockout observation window 15 minutes
Password complexity        enabled
Clear-text passwords       disabled
```

The built-in `Administrator` password was rotated after provider-console recovery was proven.

### 15.8 Advanced audit policy and Security log

Important audit subcategories were enabled/expanded to include:

```text
Logon                              Success and Failure
Account Lockout                    Success
Sensitive Privilege Use            Success and Failure
Process Creation                    Success
Audit Policy Change                Success and Failure
Authentication Policy Change       Success and Failure
Authorization Policy Change        Success and Failure
MPSSVC Rule-Level Policy Change    Success and Failure
Filtering Platform Policy Change   Success and Failure
User Account Management            Success and Failure
Security Group Management          Success and Failure
Credential Validation              Success and Failure
```

Command-line content collection for process creation was not enabled, avoiding unnecessary capture
of potentially sensitive runtime arguments. The Security event log maximum size was increased from
20 MiB to 256 MiB while retaining circular log mode:

```text
MaximumSizeInBytes = 268435456
```

### 15.9 Listener/service review status

A baseline listener inventory identified expected Windows RPC/management/system listeners plus SSH,
RDP, SMB-related listeners, WinRM, and Tailscale ports. WinRM, NetBIOS listeners, and the unnecessary
Print Spooler were addressed as documented above. Before broker calibration, perform one final
review of remaining listeners/services (including RPC-related listeners and SMB/445 behavior) and
map every unexpected listener to an approved need.

### Phase 15 completion checklist

- [x] Install and validate Windows security updates for the maintenance window.
- [x] Record Windows edition/build/update state.
- [x] Verify Defender real-time/core protections and current signatures.
- [x] Verify effective Windows Firewall default policy.
- [x] Enable useful firewall drop logging.
- [x] Configure/verify UTC and healthy time synchronization.
- [x] Disable unnecessary WinRM.
- [x] Disable unnecessary Print Spooler.
- [x] Disable SMB1.
- [x] Require SMB signing.
- [x] Disable LLMNR.
- [x] Enforce NetBIOS/file-sharing hardening on the Tailscale adapter after boot.
- [x] Harden password policy.
- [x] Configure account lockout after public administration was restricted.
- [x] Harden important advanced audit categories.
- [x] Increase Security log capacity to 256 MiB.
- [x] Rotate provider/bootstrap Administrator password.
- [ ] Review Defender tamper/cloud-protection settings supported by this Server edition/policy.
- [ ] Perform final remaining listener/service mapping and approve/disable anything unexpected.
- [ ] Decide final built-in Administrator lifecycle after all deployment recovery procedures are
  documented.
- [ ] Complete Phase 14 SSH server-side password-authentication decision.

Any unexpected listener, disabled security protection, failed time synchronization, residual public
administrative exposure, failed startup hardening task, or account-policy regression blocks broker
calibration and deployment progression.

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

For the current 0.4.0 validation milestone, the reviewed implementation checkpoint before
Windows-specific validation was:

```text
feat/mt5-broker-validation
4238464  feat: add read-only MT5 broker validation
```

Documentation commits may advance the branch beyond that implementation SHA. Record and review the
exact current commit before broker validation rather than assuming this SHA remains branch head.

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

Do not merge/tag/release v0.4.0 merely because Python-side validation passed on macOS. Windows
MetaEditor compilation and real broker read-only evidence remain release gates.

---

## Final deployment gate

A future demo deployment is blocked by any of the following:

- public SSH or RDP Windows Firewall allow rules re-enabled without an explicit approved exception;
- no tested Tailscale/private administration path;
- private access has not survived logout/reboot testing;
- SSH server authentication policy still permits an unreviewed password path at deployment time;
- unknown/unexpected listening ports or services;
- failed Tailscale startup hardening task or reappearance of NetBIOS/file-sharing bindings/listeners;
- disabled Defender/firewall protection;
- failed or ambiguous time synchronization;
- weak/regressed password, lockout, or audit policy;
- secrets committed to Git or stored with broad ACLs;
- application services bound publicly;
- broker-calibration evidence missing or stale;
- MT5 probe not compiled/reviewed;
- any accidental demo/live order-execution capability introduced into milestone 0.4.0.

Treat unexpected infrastructure state as a fail-closed condition, not as permission to continue.
