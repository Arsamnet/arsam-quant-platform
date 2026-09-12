$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location (Resolve-Path "$PSScriptRoot\..")

if ($env:OS -ne "Windows_NT") {
    throw "The guarded demo node is supported only on Windows."
}
if (-not (Test-Path ".env" -PathType Leaf)) {
    throw ".env is required."
}

uv run fx-demo-config-check
if ($LASTEXITCODE -ne 0) { throw "Configuration rejected; API was not started." }

Write-Host "Starting interactive loopback API. Press Ctrl+C to stop."
uv run fx-platform
