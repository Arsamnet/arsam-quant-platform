$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..")

if ($env:FX_TRADING_MODE -and $env:FX_TRADING_MODE -ne "paper") {
    throw "Only FX_TRADING_MODE=paper is supported."
}

uv run uvicorn fx_platform.api.main:app --host 127.0.0.1 --port 8000
