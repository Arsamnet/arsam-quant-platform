"""Non-secret demo node configuration command tests."""

from pathlib import Path

from fx_platform.demo_node_cli import main


def test_demo_config_check_prints_only_safe_status(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FX_TRADING_MODE", "paper")

    main([])

    output = capsys.readouterr().out
    assert "PLATFORM VERSION: 0.6.0" in output
    assert "TRADING MODE: PAPER" in output
    assert "EXECUTION SWITCH: DISABLED" in output
    assert "LIVE MODE: FORBIDDEN" in output
    assert "secret" not in output.lower()


def test_demo_config_check_can_return_validated_health_url(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FX_TRADING_MODE", "paper")

    main(["--health-url"])

    assert capsys.readouterr().out == "http://127.0.0.1:8000\n"
