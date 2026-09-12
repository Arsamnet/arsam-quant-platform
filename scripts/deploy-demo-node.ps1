param(
    [Parameter(Mandatory = $true)]
    [string]$Mt5DataPath,
    [switch]$InstallEA
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:OS -ne "Windows_NT") {
    throw "Guarded demo deployment is supported only on the Windows trading node."
}

Set-Location (Resolve-Path "$PSScriptRoot\..")

if (-not (Test-Path ".env" -PathType Leaf)) {
    throw ".env is required and must remain outside Git. Copy .env.example and set secrets locally."
}
if (-not (Test-Path $Mt5DataPath -PathType Container)) {
    throw "The supplied MT5 data path does not exist."
}

$Status = git status --short
if ($LASTEXITCODE -ne 0) {
    throw "Git repository state could not be verified."
}
if ($Status) {
    throw "Deployment requires a clean reviewed worktree."
}

uv sync --locked --all-extras
if ($LASTEXITCODE -ne 0) { throw "Locked dependency installation failed." }

./scripts/check.ps1
if ($LASTEXITCODE -ne 0) { throw "Quality gate failed." }

uv run fx-demo-config-check
if ($LASTEXITCODE -ne 0) { throw "Demo configuration validation failed closed." }

if ($InstallEA) {
    ./scripts/install-mt5-execution-guard.ps1 -Mt5DataPath $Mt5DataPath
}

Write-Host "Deployment checks complete. Execution was not armed and no order was placed."
