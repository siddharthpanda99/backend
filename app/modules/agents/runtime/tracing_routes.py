"""
agents/runtime/tracing_routes.py
----------------------------------
API routes for agent trace event retrieval and cost analytics.

Registered at: /api/v1/agents/traces/
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.common_lib_integration import common_memory
from common_lib.modules.orchestration.agents.agent.tracing import TraceRecorder
from common_lib.modules.orchestration.agents.agent.tracing.cost_service import (
    AgentCostService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/traces", tags=["Agent Tracing"])


def _get_recorder() -> TraceRecorder:
    """Get a TraceRecorder instance wired to the common memory store."""
    return TraceRecorder(common_memory)


def _get_cost_service() -> AgentCostService:
    """Get an AgentCostService instance wired to the common memory store."""
    return AgentCostService(common_memory)


@router.get("/session/{session_id}")
async def get_session_trace(
    session_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    event_types: Optional[str] = Query(
        default=None,
        description="Comma-separated list of event types to filter (e.g., llm_start,llm_end,tool_start)",
    ),
):
    """
    Get all trace events for a session, ordered by timestamp.

    Args:
        session_id: The chat session ID.
        limit: Max events to return (1-1000).
        offset: Pagination offset.
        event_types: Optional filter — comma-separated event types.

    Returns:
        List of serialized AgentTraceEvent dicts.
    """
    try:
        recorder = _get_recorder()
        types = (
            [t.strip() for t in event_types.split(",") if t.strip()]
            if event_types
            else None
        )
        events = recorder.get_session_trace(
            session_id=session_id,
            limit=limit,
            offset=offset,
            event_types=types,
        )
        return {"events": events, "count": len(events)}
    except Exception as e:
        logger.error(f"Failed to get session trace for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/summary")
async def get_session_trace_summary(session_id: str):
    """
    Get aggregate trace summary for a session.

    Returns:
        Dict with total_tokens, total_cost, tool_calls, llm_calls, etc.
    """
    try:
        recorder = _get_recorder()
        summary = recorder.get_session_summary(session_id=session_id)
        if summary["total_events"] == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No trace events found for session: {session_id}",
            )
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session summary for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/{agent_id}")
async def get_agent_traces(
    agent_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    Get recent trace events for an agent across sessions.

    Args:
        agent_id: The agent ID.
        limit: Max events to return.
        offset: Pagination offset.

    Returns:
        List of serialized AgentTraceEvent dicts (most recent first).
    """
    try:
        recorder = _get_recorder()
        events = recorder.get_agent_traces(
            agent_id=agent_id,
            limit=limit,
            offset=offset,
        )
        return {"events": events, "count": len(events)}
    except Exception as e:
        logger.error(f"Failed to get agent traces for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/{agent_id}/sessions")
async def get_agent_trace_sessions(
    agent_id: str,
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Get distinct session IDs with trace data for an agent.

    Returns:
        List of summaries per session (session_id, last_event_at, event_count).
    """
    try:
        recorder = _get_recorder()
        sessions = recorder.get_distinct_sessions(
            agent_id=agent_id,
            limit=limit,
        )
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        logger.error(f"Failed to get agent sessions for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/event/{event_id}")
async def get_trace_event(event_id: str):
    """
    Get a single trace event by its ID.

    Args:
        event_id: The event UUID.

    Returns:
        Serialized AgentTraceEvent dict.
    """
    try:
        recorder = _get_recorder()
        event = recorder.get_trace_by_id(event_id=event_id)
        if not event:
            raise HTTPException(
                status_code=404,
                detail=f"Trace event not found: {event_id}",
            )
        return event
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trace event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Cost Analytics Endpoints
# =========================================================================


@router.get("/cost/summary/{agent_id}")
async def get_agent_cost_summary(agent_id: str):
    """
    Get overall cost summary for an agent.

    Returns total cost, tokens, LLM calls, tool calls, and averages
    across all recorded sessions.
    """
    try:
        svc = _get_cost_service()
        return svc.get_cost_summary(agent_id=agent_id)
    except Exception as e:
        logger.error(f"Failed to get cost summary for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost/timeline/{agent_id}")
async def get_agent_cost_timeline(
    agent_id: str,
    days: int = Query(default=30, ge=1, le=365),
):
    """
    Get daily cost and token usage for the last N days.

    Args:
        agent_id: The agent ID.
        days: Number of days to look back (1-365).

    Returns:
        List of daily cost data points with cost_usd, tokens, llm_calls.
    """
    try:
        svc = _get_cost_service()
        return svc.get_cost_timeline(agent_id=agent_id, days=days)
    except Exception as e:
        logger.error(f"Failed to get cost timeline for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost/by-model/{agent_id}")
async def get_agent_cost_by_model(
    agent_id: str,
    days: int = Query(default=30, ge=1, le=365),
):
    """
    Get cost and token usage grouped by model/provider.

    Returns per-model breakdown with cost, tokens, calls, duration.
    """
    try:
        svc = _get_cost_service()
        return svc.get_cost_by_model(agent_id=agent_id, days=days)
    except Exception as e:
        logger.error(f"Failed to get cost by model for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost/by-provider/{agent_id}")
async def get_agent_cost_by_provider(
    agent_id: str,
    days: int = Query(default=30, ge=1, le=365),
):
    """
    Get cost and token usage grouped by provider (aggregated across models).

    Returns per-provider breakdown with cost, tokens, calls, model_count.
    """
    try:
        svc = _get_cost_service()
        return svc.get_cost_by_provider(agent_id=agent_id, days=days)
    except Exception as e:
        logger.error(f"Failed to get cost by provider for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost/alerts/{agent_id}")
async def get_agent_cost_alerts(
    agent_id: str,
    daily_budget: float = Query(
        default=5.0,
        ge=0.01,
        description="Daily cost budget in USD",
    ),
    model_budget: Optional[float] = Query(
        default=None,
        ge=0.01,
        description="Per-model cost budget in USD (optional)",
    ),
    session_budget: Optional[float] = Query(
        default=None,
        ge=0.01,
        description="Per-session cost budget in USD (optional)",
    ),
    days: int = Query(default=30, ge=1, le=365),
):
    """
    Check for over-budget conditions for an agent.

    Compares actual spending against configured thresholds and returns
    structured alert data with daily, model, and session-level overages.

    Args:
        agent_id: The agent to check.
        daily_budget: Max allowed cost per day in USD.
        model_budget: Max allowed cost per model in USD (optional).
        session_budget: Max allowed cost per session in USD (optional).
        days: Look-back window.

    Returns:
        Dict with summary, daily_alerts, model_alerts, session_alerts,
        and overall_status.
    """
    try:
        svc = _get_cost_service()
        return svc.check_budget_alerts(
            agent_id=agent_id,
            daily_budget_usd=daily_budget,
            model_budget_usd=model_budget,
            session_budget_usd=session_budget,
            days=days,
        )
    except Exception as e:
        logger.error(f"Failed to check budget alerts for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost/by-session/{agent_id}")
async def get_agent_cost_by_session(
    agent_id: str,
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Get cost summaries for the most recent sessions.

    Returns per-session cost, tokens, and duration data.
    """
    try:
        svc = _get_cost_service()
        return svc.get_cost_by_session(agent_id=agent_id, limit=limit)
    except Exception as e:
        logger.error(f"Failed to get cost by session for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
