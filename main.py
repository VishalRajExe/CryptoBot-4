#!/usr/bin/env python3
"""
Cryptobot - Unified Crypto Trading Bot

A fully integrated, intelligent trading system combining the best features
from 16 open-source trading repositories.

Features:
- Multi-market data with fallback chains and provenance tracking
- Multi-agent research (Market, News, Onchain, Sentiment, Macro)
- Kronos foundation model for candlestick forecasting
- Advanced portfolio optimization (HRP, NCO, Risk Parity, etc.)
- Comprehensive risk management with circuit breakers
- Paper trading engine with realistic simulation
- Vectorized + event-driven backtesting
- Web dashboard with real-time updates
- Continuous learning from trade outcomes
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from cryptobot.api.main import app
from cryptobot.config.settings import settings
from cryptobot.data.fetcher import get_fetcher, close_fetcher
from cryptobot.execution.paper import PaperEngine
from cryptobot.research.graph import ResearchGraph

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(settings.data_dir / 'logs' / 'cryptobot.log'),
    ],
)

logger = logging.getLogger(__name__)

# Global components
paper_engine: PaperEngine | None = None
research_graph: ResearchGraph | None = None
shutdown_event = asyncio.Event()


async def initialize_components() -> None:
    """Initialize all bot components."""
    global paper_engine, research_graph

    logger.info("Initializing Cryptobot components...")

    # Create data directory
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / 'logs').mkdir(parents=True, exist_ok=True)
    (settings.data_dir / 'checkpoints').mkdir(parents=True, exist_ok=True)
    (settings.data_dir / 'models').mkdir(parents=True, exist_ok=True)

    # Initialize data fetcher
    fetcher = await get_fetcher()
    logger.info("Data fetcher initialized")

    # Initialize paper trading engine
    paper_engine = PaperEngine(config={
        "slippage_bps": 2.0,
        "commission_bps": 5.0,
        "latency_ms": 50.0,
    })

    account = paper_engine.create_account(
        name="default",
        equity=100000,
        exchange="binance",
    )
    await paper_engine.start_all()
    logger.info(f"Paper engine started with account: {account.id}")

    # Initialize research graph
    research_graph = ResearchGraph(
        selected_analysts=("market", "news", "onchain", "sentiment", "macro"),
        config={
            "memory_log_path": str(settings.data_dir / "memory"),
            "checkpoint_dir": str(settings.data_dir / "checkpoints"),
            "max_debate_rounds": 3,
            "max_risk_rounds": 2,
        },
    )
    logger.info("Research graph initialized")

    logger.info("All components initialized successfully")


async def shutdown_components() -> None:
    """Gracefully shutdown all components."""
    global paper_engine, research_graph

    logger.info("Shutting down Cryptobot components...")

    if paper_engine:
        await paper_engine.stop_all()
        logger.info("Paper engine stopped")

    await close_fetcher()
    logger.info("Data fetcher closed")

    logger.info("Shutdown complete")


def signal_handler(signum: int, frame) -> None:
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, initiating shutdown...")
    shutdown_event.set()


async def main() -> None:
    """Main entry point."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize components
        await initialize_components()

        # Start API server
        config = uvicorn.Config(
            app,
            host=settings.dashboard.host,
            port=settings.dashboard.port,
            log_level=settings.log_level.lower(),
            access_log=True,
        )
        server = uvicorn.Server(config)

        # Run server and wait for shutdown
        server_task = asyncio.create_task(server.serve())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [server_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await shutdown_components()


if __name__ == "__main__":
    asyncio.run(main())