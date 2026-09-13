"""Static regression checks for the real Windows MetaEditor compile gate."""

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[2]
COMPILE_SCRIPT = REPOSITORY_ROOT / "scripts" / "compile-mt5-execution-guard.ps1"


def test_metaeditor_gate_requires_fresh_nonempty_ex5_and_exact_clean_result() -> None:
    source = COMPILE_SCRIPT.read_text(encoding="utf-8")

    derive = source.index("[System.IO.Path]::ChangeExtension")
    remove = source.index("Remove-Item -LiteralPath $CompiledArtifact")
    launch = source.index("Start-Process -FilePath $MetaEditorPath")
    assert derive < remove < launch
    assert "Test-Path $CompiledArtifact -PathType Leaf" in source
    assert "$Artifact.Length -le 0" in source
    assert "^Result:\\s+0 errors,\\s+0 warnings(?:,.*)?$" in source


def test_metaeditor_exit_code_is_evidence_not_the_success_authority() -> None:
    source = COMPILE_SCRIPT.read_text(encoding="utf-8")

    assert "$Process.ExitCode -ne 0" not in source
    assert 'Write-Host "MetaEditor ExitCode: $($Process.ExitCode)"' in source
    assert 'Write-Host "MetaEditor gate passed"' in source
    assert 'Write-Host "Compilation placed no order and did not arm the EA."' in source
