# Windows Server 2025 Hardening Runbook

Before any future demo deployment:

1. Patch Windows Server and MT5 through a controlled maintenance/reboot window; record versions.
2. Enable Microsoft Defender real-time/cloud protection and tamper protection; configure alerts.
3. Default-deny inbound Windows Firewall. Permit no public FastAPI/PostgreSQL/Redis port.
4. Restrict RDP to VPN/private administration, Network Level Authentication, MFA-capable gateway,
   named administrators, and account lockout policy. Disable unused accounts/services/protocols.
5. Run Python/MT5 services under dedicated least-privilege non-admin accounts with separate data
   directories. Deny interactive logon where operationally practical.
6. Bind FastAPI/PostgreSQL to loopback, verify with `Get-NetTCPConnection`, and test from another
   host that ports are unreachable.
7. Store secrets using protected machine/user facilities with ACLs; rotate bootstrap credentials.
8. Enable encrypted volumes/backups, time synchronization, event/audit logging, and protected log
   retention. Test restore before deployment.
9. Configure controlled automatic recovery after reboot only after health/fail-closed tests. Do not
   use Docker Desktop as a production dependency.
10. Capture a signed baseline and rollback point; run dependency audit and malware scan.

Any unexpected listener, disabled protection, failed time sync, public RDP exposure, or unsafe mode
blocks deployment.
