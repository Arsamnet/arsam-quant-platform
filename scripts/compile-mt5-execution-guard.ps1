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
$ResolvedSource = (Resolve-Path -LiteralPath $EaSourcePath).Path
if ([System.IO.Path]::GetExtension($ResolvedSource) -ine ".mq5") {
    throw "MetaEditor gate requires an .mq5 source file."
}
$CompiledArtifact = [System.IO.Path]::ChangeExtension($ResolvedSource, ".ex5")
if (Test-Path -LiteralPath $CompiledArtifact) {
    try {
        Remove-Item -LiteralPath $CompiledArtifact -Force -ErrorAction Stop
    }
    catch {
        throw "Stale EX5 artifact could not be removed; compilation is blocked."
    }
}
if (Test-Path -LiteralPath $CompiledArtifact) {
    throw "Stale EX5 artifact still exists; compilation is blocked."
}

$CompileLog = Join-Path ([System.IO.Path]::GetTempPath()) (
    "arsam-metaeditor-v050-" + [guid]::NewGuid().ToString("N") + ".log"
)

try {
    $Process = Start-Process -FilePath $MetaEditorPath -ArgumentList @(
        "/compile:$ResolvedSource",
        "/log:$CompileLog"
    ) -Wait -PassThru -ErrorAction Stop
}
catch {
    throw "MetaEditor launch or compilation wait failed; no execution is authorized."
}

Write-Host "MetaEditor ExitCode: $($Process.ExitCode)"

if (-not (Test-Path $CompileLog -PathType Leaf)) {
    throw "MetaEditor did not produce a compile log."
}
$CompileOutput = Get-Content -LiteralPath $CompileLog
$ResultLines = @($CompileOutput | Where-Object { $_ -match "^\s*Result:" })
if ($ResultLines.Count -ne 1) {
    Write-Host ($CompileOutput -join [Environment]::NewLine)
    throw "MetaEditor compile result is missing or ambiguous; no execution is authorized."
}
$ResultLine = $ResultLines[0].Trim()
Write-Host $ResultLine
if ($ResultLine -notmatch "^Result:\s+0 errors,\s+0 warnings(?:,.*)?$") {
    throw "MetaEditor gate failed; no execution is authorized."
}
if (-not (Test-Path $CompiledArtifact -PathType Leaf)) {
    throw "MetaEditor reported success but did not create a fresh EX5 artifact."
}
$Artifact = Get-Item -LiteralPath $CompiledArtifact
if ($Artifact.Length -le 0) {
    throw "MetaEditor created an empty EX5 artifact; no execution is authorized."
}

Write-Host "Source path: $ResolvedSource"
Write-Host "EX5 path: $CompiledArtifact"
Write-Host "EX5 byte size: $($Artifact.Length)"
Write-Host "MetaEditor gate passed"
Write-Host "Compilation placed no order and did not arm the EA."
