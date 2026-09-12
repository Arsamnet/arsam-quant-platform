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


def test_live_mode_fails_startup() -> None:
    with pytest.raises(ValidationError, match=r"live.*forbidden"):
        _settings(trading_mode=TradingMode.LIVE)


def test_demo_mode_requires_explicit_enablement_and_secret() -> None:
    with pytest.raises(ValidationError, match="explicit"):
        _settings(trading_mode=TradingMode.DEMO)
    with pytest.raises(ValidationError, match=r"32\+"):
        _settings(trading_mode=TradingMode.DEMO, demo_execution_enabled=True)


def _demo_settings(**changes: object) -> Settings:
    values: dict[str, object] = {
        "trading_mode": TradingMode.DEMO,
        "demo_execution_enabled": True,
        "demo_execution_secret": SecretStr("demo-test-secret-that-is-at-least-32-chars"),
    }
    values.update(changes)
    return _settings(**values)


def test_guarded_demo_configuration_is_explicit_and_fixed() -> None:
    settings = _demo_settings()

    assert settings.trading_mode is TradingMode.DEMO
    assert settings.active_node_id == "local-demo-node"
    assert settings.demo_max_volume == Decimal("0.01")
    assert settings.demo_max_open_positions == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("demo_expected_broker_company", "Wrong Broker"),
        ("demo_expected_broker_server", "Wrong Server"),
        ("demo_expected_account_currency", "EUR"),
        ("demo_expected_account_mode", "retail_netting"),
        ("demo_expected_leverage", 200),
        ("demo_allowed_symbols", frozenset({"EURUSD"})),
        ("demo_max_volume", Decimal("0.02")),
        ("demo_max_open_positions", 2),
        ("demo_magic_number", 5050002),
        ("bind_host", "localhost"),
        ("demo_require_stop_loss", False),
        ("demo_require_take_profit", False),
    ],
)
def test_demo_identity_and_exposure_policy_cannot_be_relaxed(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _demo_settings(**{field: value})


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
        {"max_daily_loss_fraction": Decimal("NaN")},
        {"max_daily_loss_absolute_cap": Decimal(-1)},
        {"max_trade_risk_fraction": Decimal("1.1")},
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


def test_runtime_rejects_allowed_symbols_without_reviewed_metadata() -> None:
    with pytest.raises(ValueError, match="symbol specification"):
        build_runtime(_settings(allowed_symbols=frozenset({"XAUUSD"})))


@pytest.mark.parametrize("legacy_name", ["max_daily_loss", "max_spread"])
def test_retired_absolute_risk_settings_fail_startup(legacy_name: str) -> None:
    with pytest.raises(ValidationError, match="retired"):
        _settings(**{legacy_name: Decimal(1)})
