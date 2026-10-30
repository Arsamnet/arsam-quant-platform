$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location (Resolve-Path "$PSScriptRoot\..")

if ($env:OS -ne "Windows_NT") {
    throw "Autonomous DEMO is supported only on the reviewed Windows trading node."
}
if (-not (Test-Path ".env" -PathType Leaf)) {
    throw ".env is required."
}

uv run fx-demo-config-check
if ($LASTEXITCODE -ne 0) {
    throw "Configuration rejected; autonomous supervisor was not started."
}

try {
    $Health = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health" -TimeoutSec 3
}
catch {
    throw "The loopback trading API must already be running before autonomous DEMO starts."
}

if ($Health.status -ne "ok" -or
    $Health.trading_mode -ne "demo" -or
    $Health.ai_mode -ne "openai") {
    throw "Loopback API is not healthy in reviewed DEMO + OpenAI mode."
}

Write-Host "Starting guarded autonomous DEMO supervisor. LIVE remains forbidden."
Write-Host "Press Ctrl+C to stop."
uv run fx-autonomous-demo
