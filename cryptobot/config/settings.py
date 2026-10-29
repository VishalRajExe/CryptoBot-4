"""
Unified configuration system using Pydantic v2.
Adapted from freqtrade configuration and Vibe-Trading pyproject.toml patterns.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExchangeConfig(BaseModel):
    """Exchange-specific configuration."""

    name: str
    enabled: bool = True
    api_key: str | None = None
    api_secret: str | None = None
    passphrase: str | None = None
    testnet: bool = True
    rate_limit: int = 1200  # requests per minute
    ws_enabled: bool = True
    markets: list[str] = Field(default_factory=lambda: ["spot", "linear", "inverse", "option"])
    options: dict[str, Any] = Field(default_factory=dict)


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: Literal["openai", "anthropic", "google", "ollama", "openai_compatible"] = "openai"
    model: str = "gpt-4o"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.1
    max_tokens: int = 8192
    reasoning_effort: Literal["low", "medium", "high"] | None = None
    timeout: int = 60
    max_retries: int = 3


class DatabaseConfig(BaseModel):
    """Database configuration."""

    type: Literal["sqlite", "postgresql"] = "sqlite"
    url: str | None = None
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False


class RedisConfig(BaseModel):
    """Redis cache configuration."""

    enabled: bool = True
    url: str = "redis://localhost:6379/0"
    ttl_seconds: int = 300
    max_connections: int = 50


class RiskConfig(BaseModel):
    """Risk management configuration."""

    max_position_pct: float = 0.1  # Max 10% per position
    max_portfolio_pct: float = 0.8  # Max 80% invested
    max_daily_loss_pct: float = 0.05  # 5% daily loss limit
    max_drawdown_pct: float = 0.15  # 15% max drawdown
    max_leverage: float = 3.0
    min_risk_reward: float = 1.5
    kelly_fraction: float = 0.25  # Fraction of Kelly
    correlation_limit: float = 0.7  # Max correlation between positions
    sector_limit_pct: float = 0.3  # Max 30% per sector
    stop_loss_pct: float = 0.02  # 2% default stop
    take_profit_pct: float = 0.04  # 4% default target


class BacktestConfig(BaseModel):
    """Backtesting configuration."""

    engine: Literal["vectorized", "event_driven", "both"] = "both"
    initial_cash: float = 100000.0
    commission: float = 0.0005  # 0.05%
    slippage: float = 0.0002  # 0.02%
    funding_rate_enabled: bool = True
    liquidation_enabled: bool = True
    max_parallel: int = 4


class DashboardConfig(BaseModel):
    """Dashboard configuration."""

    host: str = "0.0.0.0"
    port: int = 8080
    ws_port: int = 8081
    auth_enabled: bool = False
    username: str | None = None
    password_hash: str | None = None


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
    )

    # Application
    app_name: str = "Cryptobot"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"
    data_dir: Path = Path("./data")
    results_dir: Path = Path("./results")

    # Exchanges
    exchanges: dict[str, ExchangeConfig] = Field(default_factory=dict)

    # LLM Providers
    llm_providers: dict[str, LLMConfig] = Field(default_factory=dict)
    default_llm: str = "default"
    deep_thinking_llm: str = "deep"
    quick_thinking_llm: str = "quick"

    # Database & Cache
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)

    # Risk Management
    risk: RiskConfig = Field(default_factory=RiskConfig)

    # Backtesting
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)

    # Dashboard
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)

    # Data
    data_sources: dict[str, dict[str, Any]] = Field(default_factory=dict)
    default_timeframe: str = "1m"
    lookback_bars: int = 500

    # Execution
    paper_trading: bool = True
    default_exchange: str = "binance"
    order_timeout: int = 30

    # Orchestration
    agent_enabled: bool = True
    agent_heartbeat_interval: int = 30
    max_parallel_agents: int = 5

    @field_validator("data_dir", "results_dir", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        return Path(v).expanduser().resolve()

    @model_validator(mode="after")
    def validate_exchanges(self) -> Settings:
        if not self.exchanges:
            # Default exchanges for crypto
            self.exchanges = {
                "binance": ExchangeConfig(
                    name="binance",
                    testnet=True,
                    markets=["spot", "linear"],
                ),
                "bybit": ExchangeConfig(
                    name="bybit",
                    testnet=True,
                    markets=["spot", "linear", "inverse"],
                ),
                "okx": ExchangeConfig(
                    name="okx",
                    testnet=True,
                    markets=["spot", "linear"],
                ),
                "hyperliquid": ExchangeConfig(
                    name="hyperliquid",
                    testnet=True,
                    markets=["linear"],
                ),
            }
        return self

    def get_exchange(self, name: str) -> ExchangeConfig | None:
        """Get exchange config by name."""
        return self.exchanges.get(name.lower())

    def get_llm(self, tier: str = "default") -> LLMConfig:
        """Get LLM config by tier."""
        key = {
            "default": self.default_llm,
            "deep": self.deep_thinking_llm,
            "quick": self.quick_thinking_llm,
        }.get(tier, tier)
        return self.llm_providers.get(key, self.llm_providers.get("default", LLMConfig()))


# Global settings instance
settings = Settings()


def load_settings(config_path: str | Path | None = None) -> Settings:
    """Load settings from YAML config file if provided."""
    global settings
    if config_path:
        import yaml
        with open(config_path) as f:
            config_data = yaml.safe_load(f)
        settings = Settings(**config_data)
    return settings