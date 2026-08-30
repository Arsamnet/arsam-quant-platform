$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..")

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv is required. Install it from https://docs.astral.sh/uv/ and rerun."
    exit 1
}

uv sync --locked --all-extras
uv run pre-commit install
Write-Host "Bootstrap complete. Copy .env.example to .env only when local overrides are needed."
