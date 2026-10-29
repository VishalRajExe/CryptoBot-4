"""
Settings API routes.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cryptobot.config.settings import settings, load_settings

router = APIRouter()


class SettingsResponse(BaseModel):
    app_name: str
    app_version: str
    environment: str
    debug: bool
    log_level: str
    paper_trading: bool
    default_exchange: str
    default_timeframe: str
    lookback_bars: int
    risk: dict[str, Any]
    dashboard: dict[str, Any]


class ExchangeConfigUpdate(BaseModel):
    name: str
    enabled: bool | None = None
    testnet: bool | None = None
    rate_limit: int | None = None


class RiskConfigUpdate(BaseModel):
    max_position_pct: float | None = None
    max_portfolio_pct: float | None = None
    max_daily_loss_pct: float | None = None
    max_drawdown_pct: float | None = None
    max_leverage: float | None = None


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """Get current settings."""
    return SettingsResponse(
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
        debug=settings.debug,
        log_level=settings.log_level,
        paper_trading=settings.paper_trading,
        default_exchange=settings.default_exchange,
        default_timeframe=settings.default_timeframe,
        lookback_bars=settings.lookback_bars,
        risk={
            "max_position_pct": settings.risk.max_position_pct,
            "max_portfolio_pct": settings.risk.max_portfolio_pct,
            "max_daily_loss_pct": settings.risk.max_daily_loss_pct,
            "max_drawdown_pct": settings.risk.max_drawdown_pct,
            "max_leverage": settings.risk.max_leverage,
            "min_risk_reward": settings.risk.min_risk_reward,
            "kelly_fraction": settings.risk.kelly_fraction,
        },
        dashboard={
            "host": settings.dashboard.host,
            "port": settings.dashboard.port,
            "ws_port": settings.dashboard.ws_port,
            "auth_enabled": settings.dashboard.auth_enabled,
        },
    )


@router.put("/exchanges/{exchange_name}")
async def update_exchange(
    exchange_name: str,
    config: ExchangeConfigUpdate,
):
    """Update exchange configuration."""
    if exchange_name not in settings.exchanges:
        raise HTTPException(status_code=404, detail="Exchange not found")

    exchange = settings.exchanges[exchange_name]

    if config.enabled is not None:
        exchange.enabled = config.enabled
    if config.testnet is not None:
        exchange.testnet = config.testnet
    if config.rate_limit is not None:
        exchange.rate_limit = config.rate_limit

    return {"message": f"Exchange {exchange_name} updated", "exchange": exchange.model_dump()}


@router.put("/risk")
async def update_risk(config: RiskConfigUpdate):
    """Update risk configuration."""
    if config.max_position_pct is not None:
        settings.risk.max_position_pct = config.max_position_pct
    if config.max_portfolio_pct is not None:
        settings.risk.max_portfolio_pct = config.max_portfolio_pct
    if config.max_daily_loss_pct is not None:
        settings.risk.max_daily_loss_pct = config.max_daily_loss_pct
    if config.max_drawdown_pct is not None:
        settings.risk.max_drawdown_pct = config.max_drawdown_pct
    if config.max_leverage is not None:
        settings.risk.max_leverage = config.max_leverage

    return {"message": "Risk configuration updated", "risk": settings.risk.model_dump()}


@router.put("/paper_trading")
async def toggle_paper_trading(enabled: bool):
    """Toggle paper trading mode."""
    settings.paper_trading = enabled
    return {"message": f"Paper trading {'enabled' if enabled else 'disabled'}", "paper_trading": enabled}


@router.post("/reload")
async def reload_settings(config_path: str | None = None):
    """Reload settings from config file."""
    load_settings(config_path)
    return {"message": "Settings reloaded"}


@router.get("/exchanges")
async def list_exchanges():
    """List all configured exchanges."""
    return {
        name: {
            "enabled": ex.enabled,
            "testnet": ex.testnet,
            "rate_limit": ex.rate_limit,
            "markets": ex.markets,
        }
        for name, ex in settings.exchanges.items()
    }


@router.get("/llm")
async def get_llm_config():
    """Get LLM configuration (without API keys)."""
    return {
        "default": settings.get_llm("default").model_dump(exclude={"api_key"}),
        "deep": settings.get_llm("deep").model_dump(exclude={"api_key"}),
        "quick": settings.get_llm("quick").model_dump(exclude={"api_key"}),
    }


@router.get("/strategies")
async def get_strategies_config():
    """Get strategies configuration."""
    import yaml
    config_path = settings.data_dir / "config" / "strategies.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


@router.get("/risk")
async def get_risk_config():
    """Get risk configuration."""
    import yaml
    config_path = settings.data_dir / "config" / "risk.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return settings.risk.model_dump()