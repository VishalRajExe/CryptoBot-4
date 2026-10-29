#!/usr/bin/env python3
"""
Cryptobot CLI Entry Point.

Provides commands for:
- Running the bot
- Running backtests
- Running research
- Managing strategies
- Managing positions
"""

import asyncio
import logging
import sys
from pathlib import Path

import click
import numpy as np
from rich.console import Console
from rich.table import Table

from cryptobot.config.settings import settings, load_settings
from cryptobot.api.main import app
from cryptobot.execution.paper import PaperEngine
from cryptobot.research.graph import ResearchGraph
from cryptobot.backtest.engine import BacktestEngine, BacktestConfig, run_vectorized_backtest
from cryptobot.integrations.alpaca import create_alpaca_engine
from cryptobot.integrations.telegram import start_telegram_bot, TelegramConfig

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Config file path')
@click.option('--debug/--no-debug', default=False, help='Enable debug mode')
@click.pass_context
def cli(ctx, config, debug):
    """Cryptobot - Unified Crypto Trading Bot."""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config
    ctx.obj['debug'] = debug

    if config:
        load_settings(config)

    if debug:
        settings.debug = True
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option('--host', default='0.0.0.0', help='Host to bind')
@click.option('--port', default=8000, help='Port to bind')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
def serve(host, port, reload):
    """Start the API server."""
    import uvicorn
    uvicorn.run(
        "cryptobot.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=settings.log_level.lower(),
    )


@cli.command()
@click.option('--capital', default=100000, help='Initial capital')
@click.option('--exchange', default='alpaca', help='Exchange to use')
def paper(capital, exchange):
    """Start paper trading engine."""
    async def run_paper():
        if exchange == 'alpaca':
            engine = await create_alpaca_engine()
            console.print(f"[green]Alpaca paper engine started[/green]")
            console.print(f"Account: {await engine.get_account_summary()}")
            # Keep running
            await asyncio.Event().wait()
        else:
            engine = PaperEngine(config={
                "slippage_bps": 2.0,
                "commission_bps": 5.0,
                "latency_ms": 50.0,
            })
            account = engine.create_account(name="default", equity=capital)
            await engine.start_all()
            console.print(f"[green]Paper engine started with {capital} capital[/green]")
            await asyncio.Event().wait()

    asyncio.run(run_paper())


@cli.command()
@click.option('--symbols', '-s', multiple=True, required=True, help='Symbols to analyze')
@click.option('--date', '-d', help='Trade date (YYYY-MM-DD)')
@click.option('--portfolio', '-p', help='Portfolio context JSON file')
def research(symbols, date, portfolio):
    """Run multi-agent research analysis."""
    async def run_research():
        graph = ResearchGraph(
            selected_analysts=("market", "news", "onchain", "sentiment", "macro"),
            config={
                "memory_log_path": str(settings.data_dir / "memory"),
                "checkpoint_dir": str(settings.data_dir / "checkpoints"),
            },
        )

        portfolio_context = None
        if portfolio:
            import json
            with open(portfolio) as f:
                portfolio_context = json.load(f)

        result = await graph.run(
            symbols=list(symbols),
            trade_date=date,
            portfolio_context=portfolio_context,
        )

        # Display results
        console.print(f"[bold green]Research completed for {', '.join(symbols)}[/bold green]")

        if result.get('final_decision'):
            decision = result['final_decision']
            if decision.get('final_orders'):
                table = Table(title="Final Orders")
                table.add_column("Symbol")
                table.add_column("Action")
                table.add_column("Size %")
                table.add_column("Entry")
                table.add_column("SL")
                table.add_column("TP")

                for order in decision['final_orders']:
                    table.add_row(
                        order['symbol'],
                        order['action'].upper(),
                        f"{order.get('size_pct', 0)*100:.1f}%",
                        str(order.get('entry_price', 'market')),
                        str(order.get('stop_loss', 'N/A')),
                        str(order.get('take_profit', 'N/A')),
                    )
                console.print(table)

    asyncio.run(run_research())


@cli.command()
@click.option('--symbols', '-s', multiple=True, required=True)
@click.option('--strategy', default='trend_follow', help='Strategy type')
@click.option('--timeframe', default='1h', help='Timeframe')
@click.option('--start', help='Start date (YYYY-MM-DD)')
@click.option('--end', help='End date (YYYY-MM-DD)')
@click.option('--cash', default=100000, help='Initial cash')
@click.option('--commission', default=0.0005, help='Commission rate')
@click.option('--slippage', default=0.0002, help='Slippage rate')
def backtest(symbols, strategy, timeframe, start, end, cash, commission, slippage):
    """Run vectorized backtest."""
    import pandas as pd
    from datetime import datetime
    from cryptobot.data.fetcher import get_fetcher
    from cryptobot.data.models import Symbol, MarketType

    async def run_backtest():
        fetcher = await get_fetcher()

        # Fetch data
        price_data = {}
        for symbol_str in symbols:
            symbol = Symbol.from_unified(symbol_str) if ":" in symbol_str else Symbol(
                base=symbol_str.split("/")[0] if "/" in symbol_str else symbol_str,
                quote="USDT",
                exchange="binance",
                market_type=MarketType.LINEAR,
            )

            start_dt = datetime.fromisoformat(start) if start else None
            end_dt = datetime.fromisoformat(end) if end else None

            candles = await fetcher.fetch_candles(
                symbol,
                timeframe=timeframe,
                start=start_dt,
                end=end_dt,
                limit=5000,
            )

            if candles:
                df = pd.DataFrame([c.to_dict() for c in candles])
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.set_index("timestamp").sort_index()
                price_data[symbol_str] = df["close"]

        if not price_data:
            console.print("[red]No data available[/red]")
            return

        prices = pd.DataFrame(price_data)

        # Generate signals (simplified)
        import talib
        signals = pd.DataFrame(0, index=prices.index, columns=prices.columns)

        for col in prices.columns:
            close = prices[col].values
            fast_ma = talib.EMA(close, timeperiod=10)
            slow_ma = talib.EMA(close, timeperiod=30)
            signal = np.where(fast_ma > slow_ma, 1, np.where(fast_ma < slow_ma, -1, 0))
            signals[col] = signal

        config = BacktestConfig(
            initial_cash=cash,
            commission=commission,
            slippage=slippage,
        )

        result = run_vectorized_backtest(prices=prices, signals=signals)

        # Display results
        console.print(f"[bold green]Backtest completed[/bold green]")
        table = Table(title="Backtest Results")
        table.add_column("Metric")
        table.add_column("Value")

        for key, value in result.metrics.items():
            if isinstance(value, float):
                table.add_row(key, f"{value:.4f}")
            else:
                table.add_row(key, str(value))

        console.print(table)

    asyncio.run(run_backtest())


@cli.command()
@click.option('--token', envvar='TELEGRAM_BOT_TOKEN', help='Telegram bot token')
@click.option('--chat-id', envvar='TELEGRAM_CHAT_ID', help='Telegram chat ID')
def telegram(token, chat_id):
    """Start Telegram bot."""
    from cryptobot.integrations.telegram import start_telegram_bot, TelegramConfig

    async def run_telegram():
        config = TelegramConfig(
            bot_token=token or settings.telegram_bot_token,
            chat_id=chat_id or settings.telegram_chat_id,
        )
        bot = await start_telegram_bot(config)
        console.print("[green]Telegram bot started[/green]")
        await asyncio.Event().wait()

    asyncio.run(run_telegram())


@cli.command()
def dashboard():
    """Start dashboard development server."""
    import subprocess
    subprocess.run(["npm", "run", "dev"], cwd="dashboard")


@cli.command()
def init():
    """Initialize project structure and config."""
    # Create directories
    dirs = [
        settings.data_dir,
        settings.data_dir / "logs",
        settings.data_dir / "checkpoints",
        settings.data_dir / "models",
        settings.data_dir / "memory",
        settings.data_dir / "config",
        Path("logs"),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Copy config files if they don't exist
    import shutil
    config_files = [
        ("config/exchanges.yaml.example", "config/exchanges.yaml"),
        ("config/strategies.yaml.example", "config/strategies.yaml"),
        ("config/risk.yaml.example", "config/risk.yaml"),
    ]

    for src, dst in config_files:
        src_path = Path(src)
        dst_path = Path(dst)
        if not dst_path.exists() and src_path.exists():
            shutil.copy(src_path, dst_path)
            console.print(f"Created {dst}")

    console.print("[green]Project initialized[/green]")


@cli.command()
def status():
    """Show system status."""
    table = Table(title="Cryptobot Status")
    table.add_column("Component")
    table.add_column("Status")
    table.add_column("Details")

    table.add_row("Environment", settings.environment, "")
    table.add_row("Paper Trading", "Enabled" if settings.paper_trading else "Disabled", "")
    table.add_row("Default Exchange", settings.default_exchange, "")
    table.add_row("Data Directory", str(settings.data_dir), "")
    table.add_row("Log Level", settings.log_level, "")

    console.print(table)


if __name__ == "__main__":
    cli()