"""Startup safety configuration tests."""

from decimal import Decimal

import pytest
from pydantic import SecretStr, ValidationError

from fx_platform.application.factory import build_runtime
from fx_platform.config import AiMode, Settings
from fx_platform.domain.common import TradingMode


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, **values)


def test_safe_defaults_are_paper_loopback_and_ai_disabled() -> None:
    settings = _settings()

    assert settings.trading_mode is TradingMode.PAPER
    assert settings.bind_host == "127.0.0.1"
    assert settings.ai_mode is AiMode.DISABLED
    assert build_runtime(settings).executor.executed_intents == ()


@pytest.mark.parametrize("mode", [TradingMode.DEMO, TradingMode.LIVE])
def test_non_paper_modes_fail_startup(mode: TradingMode) -> None:
    with pytest.raises(ValidationError, match="paper"):
        _settings(trading_mode=mode)


def test_public_bind_address_fails_startup() -> None:
    with pytest.raises(ValidationError, match="loopback"):
        _settings(bind_host="0.0.0.0")


def test_ai_required_cannot_be_combined_with_disabled_mode() -> None:
    with pytest.raises(ValidationError, match="AI_REQUIRED"):
        _settings(ai_required=True)


def test_openai_mode_requires_environment_owned_credentials() -> None:
    with pytest.raises(ValidationError, match="requires"):
        _settings(ai_mode=AiMode.OPENAI)

    settings = _settings(
        ai_mode=AiMode.OPENAI,
        openai_api_key=SecretStr("test-placeholder"),
        openai_model="configured-model",
    )
    with pytest.raises(RuntimeError, match="adapter boundary"):
        build_runtime(settings)


@pytest.mark.parametrize(
    "changes",
    [
        {"max_volume": Decimal(0)},
        {"max_daily_loss": Decimal("NaN")},
        {"max_trade_risk_fraction": Decimal("1.1")},
        {"max_spread": Decimal(-1)},
    ],
)
def test_invalid_risk_configuration_fails_startup(changes: dict[str, Decimal]) -> None:
    with pytest.raises(ValidationError):
        _settings(**changes)


def test_invalid_log_level_and_symbol_allowlist_fail_startup() -> None:
    with pytest.raises(ValidationError, match="LOG_LEVEL"):
        _settings(log_level="verbose")
    with pytest.raises(ValidationError, match="uppercase"):
        _settings(allowed_symbols=frozenset({"eurusd"}))
