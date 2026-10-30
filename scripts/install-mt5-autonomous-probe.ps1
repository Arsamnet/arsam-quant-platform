param(
    [Parameter(Mandatory = $true)]
    [string]$Mt5DataPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:OS -ne "Windows_NT") {
    throw "The autonomous MT5 snapshot probe can only be installed on Windows."
}

$RepositoryRoot = Resolve-Path "$PSScriptRoot\.."
$Source = Join-Path $RepositoryRoot "mt5\autonomous_probe\ArsamAutonomousSnapshotProbe.mq5"
$ExpertsDirectory = Join-Path $Mt5DataPath "MQL5\Experts\ArsamQuant"

if (-not (Test-Path $Source -PathType Leaf)) {
    throw "Reviewed autonomous snapshot source is missing: $Source"
}
if (-not (Test-Path $Mt5DataPath -PathType Container)) {
    throw "The supplied MT5 data path does not exist: $Mt5DataPath"
}

New-Item -ItemType Directory -Path $ExpertsDirectory -Force | Out-Null
Copy-Item -LiteralPath $Source -Destination $ExpertsDirectory -Force

Write-Host "Read-only autonomous snapshot source copied to $ExpertsDirectory"
Write-Host "No compilation, terminal launch, arming, or order was performed."
Write-Host "Compile the exact source in MetaEditor and require 0 errors / 0 warnings."
