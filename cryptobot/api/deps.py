"""
FastAPI dependencies.
"""

from __future__ import annotations

from typing import Any

from cryptobot.execution.paper import PaperEngine
from cryptobot.research.graph import ResearchGraph
from fastapi import WebSocket

# Global paper engine instance
_paper_engine: PaperEngine | None = None
_research_graph: ResearchGraph | None = None
_websocket_clients: set[WebSocket] = set()


def get_paper_engine() -> PaperEngine:
    """Get the global paper engine instance."""
    if _paper_engine is None:
        raise RuntimeError("Paper engine not initialized")
    return _paper_engine


def set_paper_engine(engine: PaperEngine) -> None:
    """Set the global paper engine instance."""
    global _paper_engine
    _paper_engine = engine


def get_research_graph() -> ResearchGraph | None:
    """Get the global research graph instance."""
    return _research_graph


def set_research_graph(graph: ResearchGraph) -> None:
    """Set the global research graph instance."""
    global _research_graph
    _research_graph = graph


def get_websocket_clients() -> set[WebSocket]:
    """Get the set of connected WebSocket clients."""
    return _websocket_clients


async def broadcast_update(event_type: str, data: dict) -> None:
    """Broadcast update to all connected WebSocket clients."""
    for client in _websocket_clients:
        try:
            await client.send_json({
                "type": event_type,
                "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
                "data": data,
            })
        except Exception:
            pass