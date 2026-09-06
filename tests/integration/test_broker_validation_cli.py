"""Offline CLI import, validation, diff, malformed, and blocking behavior."""

import json
from pathlib import Path

from fx_platform.broker_validation.cli import diff_main, import_main, validate_main
from tests.unit.broker_validation.helpers import FIXTURE_PATH, raw_fixture


def test_import_cli_archives_canonical_snapshot_and_prints_hashes(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "canonical.json"

    exit_code = import_main(["--input", str(FIXTURE_PATH), "--output", str(output)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "snapshot_fingerprint=" in captured.out
    assert "contract_fingerprint=" in captured.out
    assert json.loads(output.read_text(encoding="utf-8"))["mode"] == ("read_only_metadata_probe")


def test_validation_cli_writes_deterministic_report(tmp_path: Path, capsys) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    arguments = [
        "--snapshot",
        str(FIXTURE_PATH),
        "--symbol",
        "EURUSD",
        "--as-of",
        "2026-08-31T10:00:00Z",
        "--expected-broker-company",
        "SYNTHETIC TEST BROKER - NOT FIBOGROUP DATA",
        "--expected-broker-server",
        "SYNTHETIC-DEMO - NOT BROKER CALIBRATED",
    ]

    first_exit = validate_main([*arguments, "--output", str(first)])
    first_output = capsys.readouterr().out
    second_exit = validate_main([*arguments, "--output", str(second)])

    assert first_exit == second_exit == 0
    assert "status=pass" in first_output
    assert first.read_bytes() == second.read_bytes()
    report = json.loads(first.read_text(encoding="utf-8"))
    assert report["readiness"] == "ready"
    assert report["platform_version"] == "0.4.0"


def test_validation_cli_returns_blocking_exit_and_report(tmp_path: Path, capsys) -> None:
    raw = raw_fixture()
    raw["symbols"][0]["contract_size"] = "99999"
    snapshot = tmp_path / "blocking.json"
    report = tmp_path / "report.json"
    snapshot.write_text(json.dumps(raw), encoding="utf-8")

    exit_code = validate_main(
        [
            "--snapshot",
            str(snapshot),
            "--symbol",
            "EURUSD",
            "--as-of",
            "2026-08-31T10:00:00Z",
            "--expected-broker-company",
            "SYNTHETIC TEST BROKER - NOT FIBOGROUP DATA",
            "--expected-broker-server",
            "SYNTHETIC-DEMO - NOT BROKER CALIBRATED",
            "--output",
            str(report),
        ]
    )

    assert exit_code == 3
    assert "blocking_mismatch" in capsys.readouterr().out
    assert json.loads(report.read_text(encoding="utf-8"))["readiness"] == "not_ready"


def test_cli_rejects_malformed_snapshot_and_naive_time(tmp_path: Path, capsys) -> None:
    malformed = tmp_path / "bad.json"
    malformed.write_text("{}", encoding="utf-8")

    assert import_main(["--input", str(malformed)]) == 2
    assert "failed" in capsys.readouterr().err
    assert (
        validate_main(
            [
                "--snapshot",
                str(FIXTURE_PATH),
                "--symbol",
                "EURUSD",
                "--as-of",
                "2026-08-31T10:00:00",
            ]
        )
        == 2
    )
    assert "UTC offset" in capsys.readouterr().err


def test_diff_cli_classifies_quote_only_change_as_dynamic(tmp_path: Path, capsys) -> None:
    raw = raw_fixture()
    raw["acquired_at"] = "2026-08-31T10:01:00Z"
    raw["symbols"][0]["observed_at"] = "2026-08-31T10:01:00Z"
    raw["symbols"][0]["bid"] = "1.10100"
    raw["symbols"][0]["ask"] = "1.10120"
    changed = tmp_path / "changed.json"
    output = tmp_path / "diff.json"
    changed.write_text(json.dumps(raw), encoding="utf-8")

    exit_code = diff_main(
        [
            "--before",
            str(FIXTURE_PATH),
            "--after",
            str(changed),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert "contract_changed=false" in capsys.readouterr().out
    assert json.loads(output.read_text(encoding="utf-8"))["dynamic_changes"]


def test_import_cli_verifies_expected_fingerprint(capsys) -> None:
    exit_code = import_main(["--input", str(FIXTURE_PATH), "--expect-fingerprint", "0" * 64])

    assert exit_code == 2
    assert "fingerprint" in capsys.readouterr().err
