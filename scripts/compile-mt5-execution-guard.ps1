param(
    [Parameter(Mandatory = $true)]
    [string]$MetaEditorPath,
    [string]$EaSourcePath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:OS -ne "Windows_NT") {
    throw "MetaEditor compilation is a Windows-only gate."
}
if (-not (Test-Path $MetaEditorPath -PathType Leaf)) {
    throw "MetaEditor executable was not found."
}

$RepositoryRoot = Resolve-Path "$PSScriptRoot\.."
if (-not $EaSourcePath) {
    $EaSourcePath = Join-Path $RepositoryRoot "mt5\execution_guard\ArsamDemoExecutionGuard.mq5"
}
$ResolvedSource = Resolve-Path $EaSourcePath
$CompileLog = Join-Path ([System.IO.Path]::GetTempPath()) (
    "arsam-metaeditor-v050-" + [guid]::NewGuid().ToString("N") + ".log"
)

$Process = Start-Process -FilePath $MetaEditorPath -ArgumentList @(
    "/compile:$ResolvedSource",
    "/log:$CompileLog"
) -Wait -PassThru

if (-not (Test-Path $CompileLog -PathType Leaf)) {
    throw "MetaEditor did not produce a compile log."
}
$Result = Get-Content -LiteralPath $CompileLog -Raw
if ($Process.ExitCode -ne 0 -or $Result -notmatch "0 errors, 0 warnings") {
    Write-Host $Result
    throw "MetaEditor gate failed; no execution is authorized."
}

Write-Host $Result
Write-Host "MetaEditor gate passed for: $ResolvedSource"
Write-Host "Compilation placed no order and did not arm the EA."
