"""
Knowledge Engine — Provenance Routes.

Thin transport for provenance tracking.
Delegates to common_lib.modules.knowledge_engine.services.provenance_service.ProvenanceService
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.services.provenance_service import (
    ProvenanceEventType,
    ProvenanceRecord,
    ProvenanceGraph,
    get_provenance_service,
)

router = APIRouter(prefix="/provenance", tags=["Knowledge Engine — Provenance"])


# ── Request/Response Models ────────────────────────────────────


class ProvenanceRecordRequest(BaseModel):
    event_type: ProvenanceEventType
    target_type: str
    target_id: str
    actor_id: str | None = None
    actor_type: str = "system"
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    diff: dict[str, Any] | None = None
    reason: str | None = None
    tool_id: str | None = None
    workflow_id: str | None = None
    session_id: str | None = None
    parent_event_ids: list[UUID] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProvenanceRecordResponse(BaseModel):
    event: ProvenanceRecord


class ProvenanceHistoryResponse(BaseModel):
    events: list[ProvenanceRecord]


class ProvenanceGraphResponse(BaseModel):
    graph: ProvenanceGraph


class ProvenanceTimelineResponse(BaseModel):
    events: list[ProvenanceRecord]


# ── Dependency Injection ────────────────────────────────────────


def get_service() -> Any:
    """Get provenance service instance."""
    return get_provenance_service()


# ── Routes ─────────────────────────────────────────────────────


@router.post("", response_model=ProvenanceRecordResponse, status_code=201)
async def record_provenance_event(
    request: ProvenanceRecordRequest,
    service=Depends(get_service),
):
    """Record a provenance event."""
    try:
        event = await service.record_event(
            event_type=request.event_type,
            target_type=request.target_type,
            target_id=request.target_id,
            actor_id=request.actor_id,
            actor_type=request.actor_type,
            before_state=request.before_state,
            after_state=request.after_state,
            diff=request.diff,
            reason=request.reason,
            tool_id=request.tool_id,
            workflow_id=request.workflow_id,
            session_id=request.session_id,
            parent_event_ids=request.parent_event_ids,
            derived_from=request.derived_from,
            metadata=request.metadata,
        )
        return ProvenanceRecordResponse(event=event)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to record provenance event: {exc}"
        ) from exc


@router.get(
    "/history/{target_type}/{target_id}", response_model=ProvenanceHistoryResponse
)
async def get_provenance_history(
    target_type: str,
    target_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    service=Depends(get_service),
):
    """Get provenance history for an object."""
    try:
        events = await service.get_history(target_type, target_id, limit=limit)
        return ProvenanceHistoryResponse(events=events)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get provenance history: {exc}"
        ) from exc


@router.get("/graph/{target_type}/{target_id}", response_model=ProvenanceGraphResponse)
async def get_provenance_graph(
    target_type: str,
    target_id: str,
    depth: int = Query(3, ge=1, le=10, description="Traversal depth"),
    service=Depends(get_service),
):
    """Get provenance graph for an object."""
    try:
        graph = await service.get_graph(target_type, target_id, depth=depth)
        return ProvenanceGraphResponse(graph=graph)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get provenance graph: {exc}"
        ) from exc


@router.get("/actor/{actor_id}", response_model=ProvenanceHistoryResponse)
async def get_actor_activity(
    actor_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    service=Depends(get_service),
):
    """Get activity for a specific actor."""
    try:
        events = await service.get_actor_activity(actor_id, limit=limit)
        return ProvenanceHistoryResponse(events=events)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get actor activity: {exc}"
        ) from exc


@router.get("/timeline", response_model=ProvenanceTimelineResponse)
async def get_provenance_timeline(
    start_time: str | None = Query(None, description="Start time (ISO format)"),
    end_time: str | None = Query(None, description="End time (ISO format)"),
    event_types: list[ProvenanceEventType] | None = Query(
        None, description="Filter by event types"
    ),
    target_types: list[str] | None = Query(None, description="Filter by target types"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    service=Depends(get_service),
):
    """Get provenance timeline across all objects."""
    try:
        events = await service.get_timeline(
            start_time=start_time,
            end_time=end_time,
            event_types=event_types,
            target_types=target_types,
            limit=limit,
        )
        return ProvenanceTimelineResponse(events=events)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get provenance timeline: {exc}"
        ) from exc
