"""GPT Builder — Session Management Routes.

Endpoints for creating, listing, and terminating sessions,
plus context sync management and tool calls from widgets.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from common_lib.modules.gpt_builder.schemas import (
    GptBuilderSessionCreate,
    GptBuilderSessionResponse,
    GptBuilderTurnResponse,
    ToolCallRequest,
)
from common_lib.modules.gpt_builder.service import get_gpt_builder_service

router = APIRouter()


@router.post("/{app_id}/sessions", response_model=GptBuilderSessionResponse, status_code=201)
async def create_session(app_id: str, data: GptBuilderSessionCreate):
    service = get_gpt_builder_service()
    try:
        session = await service.create_session(
            app_id=app_id,
            user_id=data.user_id,
            metadata_json=data.metadata_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _session_to_response(session)


@router.get("/{app_id}/sessions", response_model=Dict[str, Any])
async def list_sessions(
    app_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    service = get_gpt_builder_service()
    sessions, total = await service.list_sessions(app_id, limit=limit, offset=offset)
    return {
        "items": [_session_to_response(s) for s in sessions],
        "total": total,
    }


@router.get("/sessions/{session_id}", response_model=GptBuilderSessionResponse)
async def get_session(session_id: str):
    service = get_gpt_builder_service()
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_response(session)


@router.delete("/sessions/{session_id}", status_code=204)
async def terminate_session(session_id: str):
    service = get_gpt_builder_service()
    success = await service.terminate_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return None


@router.get("/sessions/{session_id}/turns", response_model=List[GptBuilderTurnResponse])
async def get_turns(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    service = get_gpt_builder_service()
    turns = await service.get_turns(session_id, limit=limit, offset=offset)
    return [_turn_to_response(t) for t in turns]


@router.get("/sessions/{session_id}/context", response_model=Dict[str, Any])
async def get_context(session_id: str):
    service = get_gpt_builder_service()
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.active_context_sync or {}


@router.put("/sessions/{session_id}/context", response_model=Dict[str, Any])
async def update_context(session_id: str, context_sync: Dict[str, Any]):
    service = get_gpt_builder_service()
    success = await service.update_context_sync(session_id, context_sync)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return context_sync


@router.post("/sessions/{session_id}/tool-call", response_model=Dict[str, Any])
async def direct_tool_call(session_id: str, data: ToolCallRequest):
    from common_lib.modules.gpt_builder.tool_executor import ToolExecutor

    service = get_gpt_builder_service()
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    executor = ToolExecutor()
    result = await executor.execute_tool(
        tool_name=data.tool_name,
        arguments=data.arguments,
        app_id=session.app_id,
    )
    return result


@router.post("/sessions/{session_id}/clear", response_model=Dict[str, Any])
async def clear_session(session_id: str):
    """Clear all messages in a session (reset conversation)."""
    service = get_gpt_builder_service()
    result = await service.clear_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════

def _session_to_response(session) -> GptBuilderSessionResponse:
    return GptBuilderSessionResponse(
        id=session.id,
        app_id=session.app_id,
        user_id=session.user_id,
        started_at=session.started_at,
        last_active_at=session.last_active_at,
        message_count=session.message_count or 0,
        token_count=session.token_count or 0,
        active_context_sync=session.active_context_sync or {},
        status=session.status or "active",
        metadata_json=session.metadata_json or {},
    )


def _turn_to_response(turn) -> GptBuilderTurnResponse:
    return GptBuilderTurnResponse(
        id=turn.id,
        session_id=turn.session_id,
        sequence=turn.sequence,
        role=turn.role,
        content=turn.content,
        widgets=turn.widgets,
        context_sync=turn.context_sync,
        tool_calls=turn.tool_calls,
        tool_results=turn.tool_results,
        token_count_input=turn.token_count_input,
        token_count_output=turn.token_count_output,
        latency_ms=turn.latency_ms,
        model_id=turn.model_id,
        timestamp=turn.timestamp,
        error=turn.error,
    )
