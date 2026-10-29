"""
Research API routes.
"""

from __future__ import annotations

from typing import Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel

from cryptobot.research.graph import ResearchGraph
from cryptobot.api.deps import get_research_graph, broadcast_update

router = APIRouter()


class ResearchRequest(BaseModel):
    symbols: list[str]
    trade_date: str | None = None
    portfolio_context: dict[str, Any] | None = None


class ResearchResponse(BaseModel):
    research_id: str
    status: str
    symbols: list[str]
    trade_date: str
    final_decision: dict[str, Any] | None = None
    analyses: dict[str, Any] | None = None
    created_at: str
    completed_at: str | None = None


# In-memory storage
_research_results: dict[str, dict] = {}


@router.post("/analyze", response_model=ResearchResponse)
async def run_research(
    request: ResearchRequest,
    background_tasks: BackgroundTasks,
    graph: ResearchGraph = Depends(get_research_graph),
):
    """Run multi-agent research analysis."""
    import uuid
    research_id = str(uuid.uuid4())[:8]
    trade_date = request.trade_date or datetime.utcnow().strftime("%Y-%m-%d")

    _research_results[research_id] = {
        "research_id": research_id,
        "status": "running",
        "symbols": request.symbols,
        "trade_date": trade_date,
        "created_at": datetime.utcnow().isoformat(),
    }

    # Run in background
    background_tasks.add_task(
        _run_research_task,
        research_id,
        request.symbols,
        trade_date,
        request.portfolio_context,
        graph,
    )

    return ResearchResponse(
        research_id=research_id,
        status="running",
        symbols=request.symbols,
        trade_date=trade_date,
        created_at=datetime.utcnow().isoformat(),
    )


async def _run_research_task(
    research_id: str,
    symbols: list[str],
    trade_date: str,
    portfolio_context: dict | None,
    graph: ResearchGraph,
):
    """Background task to run research."""
    try:
        result = await graph.run(
            symbols=symbols,
            trade_date=trade_date,
            portfolio_context=portfolio_context,
        )

        _research_results[research_id].update({
            "status": "completed",
            "final_decision": result.get("final_decision"),
            "analyses": {k: v for k, v in result.items() if k.endswith("_analysis")},
            "debate_history": result.get("debate_history", []),
            "risk_debate": result.get("risk_debate", []),
            "memory_context": result.get("memory_context"),
            "errors": result.get("errors", []),
            "completed_at": datetime.utcnow().isoformat(),
        })

        # Broadcast completion
        await broadcast_update("research_completed", {
            "research_id": research_id,
            "symbols": symbols,
            "decision": result.get("final_decision"),
        })

    except Exception as e:
        _research_results[research_id].update({
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.utcnow().isoformat(),
        })


@router.get("/{research_id}", response_model=ResearchResponse)
async def get_research(research_id: str):
    """Get research result."""
    if research_id not in _research_results:
        raise HTTPException(status_code=404, detail="Research not found")

    result = _research_results[research_id]
    return ResearchResponse(
        research_id=research_id,
        status=result.get("status", "unknown"),
        symbols=result.get("symbols", []),
        trade_date=result.get("trade_date", ""),
        final_decision=result.get("final_decision"),
        analyses={k: v for k, v in result.items() if k.endswith("_analysis")},
        created_at=result.get("created_at", ""),
        completed_at=result.get("completed_at"),
    )


@router.get("", response_model=list[ResearchResponse])
async def list_research():
    """List all research runs."""
    return [
        ResearchResponse(
            research_id=k,
            status=v.get("status", "unknown"),
            symbols=v.get("symbols", []),
            trade_date=v.get("trade_date", ""),
            final_decision=v.get("final_decision"),
            created_at=v.get("created_at", ""),
            completed_at=v.get("completed_at"),
        )
        for k, v in _research_results.items()
    ]


@router.get("/{research_id}/analyses")
async def get_analyses(research_id: str):
    """Get detailed analyst outputs."""
    if research_id not in _research_results:
        raise HTTPException(status_code=404, detail="Research not found")

    result = _research_results[research_id]
    return {
        k: v for k, v in result.items()
        if k.endswith("_analysis")
    }


@router.get("/{research_id}/debate")
async def get_debate(research_id: str):
    """Get debate history."""
    if research_id not in _research_results:
        raise HTTPException(status_code=404, detail="Research not found")

    result = _research_results[research_id]
    return {
        "debate_history": result.get("debate_history", []),
        "risk_debate": result.get("risk_debate", []),
    }


@router.get("/{research_id}/memory")
async def get_memory_context(research_id: str):
    """Get memory context used."""
    if research_id not in _research_results:
        raise HTTPException(status_code=404, detail="Research not found")

    result = _research_results[research_id]
    return {
        "memory_context": result.get("memory_context"),
        "settled_decisions": result.get("settled_decisions"),
    }


@router.post("/{research_id}/settle")
async def settle_decisions(
    research_id: str,
    graph: ResearchGraph = Depends(get_research_graph),
):
    """Manually trigger decision settlement."""
    if research_id not in _research_results:
        raise HTTPException(status_code=404, detail="Research not found")

    settled = await graph.settlement_engine.settle_pending()
    _research_results[research_id]["settled_decisions"] = settled

    return {
        "message": f"Settled {len(settled)} decisions",
        "settled": settled,
    }