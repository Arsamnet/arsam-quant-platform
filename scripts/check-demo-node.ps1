$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location (Resolve-Path "$PSScriptRoot\..")

uv run fx-demo-config-check
if ($LASTEXITCODE -ne 0) { throw "Configuration rejected." }

[string]$ApiUrl = uv run fx-demo-config-check --health-url
if ($LASTEXITCODE -ne 0) { throw "Could not resolve the validated loopback URL." }
$ApiUrl = $ApiUrl.Trim()
$Health = Invoke-RestMethod -Method Get -Uri "$ApiUrl/health" -TimeoutSec 3
if ($Health.status -ne "ok" -or $Health.trading_mode -ne "demo") {
    throw "Local API health or mode check failed."
}

Write-Host "Loopback API is healthy in DEMO mode. LIVE MODE remains FORBIDDEN."
Write-Host "This check did not arm the EA or place an order."
