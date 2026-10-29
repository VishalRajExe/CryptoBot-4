"""
FastAPI backend for the trading bot.
Adapted from Vibe-Trading's api_server and OpenTerminalUI's backend.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from cryptobot.config.settings import settings
from cryptobot.data.fetcher import get_fetcher, close_fetcher
from cryptobot.execution.paper import PaperEngine
from cryptobot.research.graph import ResearchGraph
from cryptobot.backtest.engine import BacktestEngine, BacktestConfig
from cryptobot.api.routes import strategies, positions, orders, backtest, research, settings as settings_routes
from cryptobot.api.deps import set_paper_engine, set_research_graph

logger = logging.getLogger(__name__)


# Global state
paper_engine: PaperEngine | None = None
research_graph: ResearchGraph | None = None
websocket_clients: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global research_graph, paper_engine

    # Startup
    logger.info("Starting Cryptobot API...")

    # Initialize data fetcher
    fetcher = await get_fetcher()
    logger.info("Data fetcher initialized")

    # Initialize paper engine
    from cryptobot.api.deps import set_paper_engine
    paper_engine = PaperEngine(config={
        "slippage_bps": 2.0,
        "commission_bps": 5.0,
        "latency_ms": 50.0,
    })

    # Create default paper account
    account = paper_engine.create_account(
        name="default",
        equity=100000,
        exchange="binance",
    )
    await paper_engine.start_all()
    logger.info(f"Paper engine started with account: {account.id}")

    # Set paper engine in deps
    set_paper_engine(paper_engine)

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

    # Set research graph in deps
    from cryptobot.api.deps import set_research_graph
    set_research_graph(research_graph)

    yield

    # Shutdown
    logger.info("Shutting down Cryptobot API...")
    await paper_engine.stop_all()
    await close_fetcher()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Cryptobot API",
    description="Unified Crypto Trading Bot API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["strategies"])
app.include_router(positions.router, prefix="/api/v1/positions", tags=["positions"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["backtest"])
app.include_router(research.router, prefix="/api/v1/research", tags=["research"])
app.include_router(settings_routes.router, prefix="/api/v1/settings", tags=["settings"])


# WebSocket for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle incoming messages if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
        "paper_engine": paper_engine is not None and getattr(paper_engine, "_running", False),
        "research_graph": research_graph is not None,
    }


# Root endpoint
@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cryptobot API</title>
        <style>
            body { font-family: system-ui; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #1a1a2e; }
            .endpoint { background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 4px; }
            .method { font-weight: bold; color: #e94560; }
        </style>
    </head>
    <body>
        <h1>🤖 Cryptobot API</h1>
        <p>Unified Crypto Trading Bot - API Server</p>
        <h2>Endpoints</h2>
        <div class="endpoint"><span class="method">GET</span> /health - Health check</div>
        <div class="endpoint"><span class="method">GET</span> /api/v1/strategies - List strategies</div>
        <div class="endpoint"><span class="method">POST</span> /api/v1/strategies - Create strategy</div>
        <div class="endpoint"><span class="method">GET</span> /api/v1/positions - Current positions</div>
        <div class="endpoint"><span class="method">GET</span> /api/v1/orders - Order history</div>
        <div class="endpoint"><span class="method">POST</span> /api/v1/backtest - Run backtest</div>
        <div class="endpoint"><span class="method">POST</span> /api/v1/research/analyze - Run research analysis</div>
        <div class="endpoint"><span class="method">WS</span> /ws - Real-time updates</div>
        <p><a href="/docs">API Documentation (Swagger UI)</a></p>
        <p><a href="/redoc">API Documentation (ReDoc)</a></p>
    </body>
    </html>
    """


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return HTTPException(status_code=500, detail="Internal server error")


# Dependency to get paper engine
def get_paper_engine() -> PaperEngine:
    if paper_engine is None:
        raise HTTPException(status_code=503, detail="Paper engine not initialized")
    return paper_engine


def get_research_graph() -> ResearchGraph:
    if research_graph is None:
        raise HTTPException(status_code=503, detail="Research graph not initialized")
    return research_graph


# Broadcast helper
async def broadcast_update(event_type: str, data: dict):
    """Broadcast update to all WebSocket clients."""
    await manager.broadcast({
        "type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "cryptobot.api.main:app",
        host=settings.dashboard.host,
        port=settings.dashboard.port,
        reload=settings.debug,
    )