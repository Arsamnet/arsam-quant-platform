param(
    [Parameter(Mandatory = $true)]
    [string]$Mt5DataPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:OS -ne "Windows_NT") {
    throw "The MT5 execution guard can only be installed on Windows."
}

$RepositoryRoot = Resolve-Path "$PSScriptRoot\.."
$Source = Join-Path $RepositoryRoot "mt5\execution_guard\ArsamDemoExecutionGuard.mq5"
$ExpertsDirectory = Join-Path $Mt5DataPath "MQL5\Experts\ArsamQuant"

if (-not (Test-Path $Source -PathType Leaf)) {
    throw "Reviewed EA source is missing: $Source"
}
if (-not (Test-Path $Mt5DataPath -PathType Container)) {
    throw "The supplied MT5 data path does not exist: $Mt5DataPath"
}

New-Item -ItemType Directory -Path $ExpertsDirectory -Force | Out-Null
Copy-Item -LiteralPath $Source -Destination $ExpertsDirectory -Force

Write-Host "EA source copied to $ExpertsDirectory"
Write-Host "No compilation, terminal launch, arming, or order was performed."
Write-Host "Compile in MetaEditor and require 0 errors / 0 warnings before testing."
