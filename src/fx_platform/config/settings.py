"""Secure settings with paper-only and loopback-only startup validation."""

from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from fx_platform.domain.common import TradingMode


class AiMode(StrEnum):
    """Configured advisory adapter mode."""

    DISABLED = "disabled"
    OPENAI = "openai"


class Settings(BaseSettings):
    """Environment-owned runtime configuration; no secret default values are provided."""

    model_config = SettingsConfigDict(
        env_prefix="FX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    trading_mode: TradingMode = TradingMode.PAPER
    bind_host: str = "127.0.0.1"
    bind_port: int = Field(default=8000, ge=1, le=65535)
    node_id: str = Field(default="local-paper-node", min_length=1, max_length=64)
    allowed_symbols: frozenset[str] = frozenset({"EURUSD", "GBPUSD", "USDJPY"})
    ai_mode: AiMode = AiMode.DISABLED
    ai_required: bool = False
    openai_api_key: SecretStr | None = None
    openai_model: str | None = None
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://fx_platform:CHANGE_ME@127.0.0.1:5432/fx_platform"
    )
    hmac_secret: SecretStr | None = None
    log_level: str = "INFO"
    max_volume: Decimal = Decimal("0.10")
    max_open_positions: int = Field(default=3, ge=1)
    max_daily_loss_fraction: Decimal = Decimal("0.02")
    max_daily_loss_absolute_cap: Decimal | None = Decimal(200)
    max_trade_risk_fraction: Decimal = Decimal("0.01")
    max_daily_loss: Decimal | None = Field(default=None, exclude=True)
    max_spread: Decimal | None = Field(default=None, exclude=True)
    economic_calendar_required: bool = False

    @field_validator("bind_host")
    @classmethod
    def validate_loopback(cls, value: str) -> str:
        """Prevent accidental public exposure of the internal trading API."""
        if value not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("FX_BIND_HOST must be a loopback address during bootstrap")
        return value

    @field_validator("allowed_symbols")
    @classmethod
    def validate_symbols(cls, value: frozenset[str]) -> frozenset[str]:
        """Require an explicit uppercase allowlist."""
        if not value or any(not symbol or symbol != symbol.upper() for symbol in value):
            raise ValueError("FX_ALLOWED_SYMBOLS must contain uppercase symbols")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Normalize and constrain standard Python log levels."""
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("FX_LOG_LEVEL is invalid")
        return normalized

    @model_validator(mode="after")
    def enforce_safe_mode(self) -> Self:
        """Fail startup for demo/live and inconsistent AI configuration."""
        if self.trading_mode is not TradingMode.PAPER:
            raise ValueError(
                "Only FX_TRADING_MODE=paper is supported; demo/live trading is disabled"
            )
        if self.ai_required and self.ai_mode is AiMode.DISABLED:
            raise ValueError("FX_AI_REQUIRED=true cannot be used with FX_AI_MODE=disabled")
        if self.ai_mode is AiMode.OPENAI and (
            self.openai_api_key is None
            or not self.openai_api_key.get_secret_value()
            or not self.openai_model
        ):
            raise ValueError("OpenAI mode requires FX_OPENAI_API_KEY and FX_OPENAI_MODEL")
        if self.max_daily_loss is not None:
            raise ValueError(
                "FX_MAX_DAILY_LOSS is retired; configure FX_MAX_DAILY_LOSS_FRACTION and "
                "FX_MAX_DAILY_LOSS_ABSOLUTE_CAP"
            )
        if self.max_spread is not None:
            raise ValueError(
                "FX_MAX_SPREAD is retired; spread limits are defined per symbol in ticks"
            )
        for field_name, value in (
            ("max_volume", self.max_volume),
            ("max_daily_loss_fraction", self.max_daily_loss_fraction),
            ("max_trade_risk_fraction", self.max_trade_risk_fraction),
        ):
            if not value.is_finite() or value <= Decimal(0):
                raise ValueError(f"{field_name} must be a positive finite decimal")
        if self.max_daily_loss_absolute_cap is not None and (
            not self.max_daily_loss_absolute_cap.is_finite()
            or self.max_daily_loss_absolute_cap <= Decimal(0)
        ):
            raise ValueError("max_daily_loss_absolute_cap must be a positive finite decimal")
        for field_name, fraction in (
            ("max_daily_loss_fraction", self.max_daily_loss_fraction),
            ("max_trade_risk_fraction", self.max_trade_risk_fraction),
        ):
            if fraction > Decimal(1):
                raise ValueError(f"{field_name} must not exceed one")
        return self
