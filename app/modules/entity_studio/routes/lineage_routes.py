#!/usr/bin/env python3
"""
Entity Studio Lineage Routes — Thin HTTP transport for lineage/audit operations.
"""

from fastapi import APIRouter, HTTPException, Query
from common_lib.modules.entity_studio.lineage import get_lineage_tracker

router = APIRouter()


@router.get("/{entity_type}/{entity_id}")
async def get_entity_lineage(entity_type: str, entity_id: str):
    """Get full lineage/audit trail for a specific entity."""
    if entity_type not in ("atom", "molecule", "organism"):
        raise HTTPException(status_code=400, detail="Invalid entity_type")
    tracker = get_lineage_tracker()
    entries = tracker.get_entity_lineage(entity_type, entity_id)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "lineage": [entry.__dict__ for entry in entries],
    }


@router.get("/actor/{actor}")
async def get_actor_lineage(actor: str):
    """Get all activity for a specific actor/agent."""
    tracker = get_lineage_tracker()
    entries = tracker.get_actor_activity(actor)
    return {
        "actor": actor,
        "activity": [entry.__dict__ for entry in entries],
    }


@router.get("/session/{session_id}")
async def get_session_lineage(session_id: str):
    """Get all activity for a specific session."""
    tracker = get_lineage_tracker()
    entries = tracker.get_session_activity(session_id)
    return {
        "session_id": session_id,
        "activity": [entry.__dict__ for entry in entries],
    }


@router.get("/recent")
async def get_recent_lineage(
    limit: int = Query(default=100, ge=1, le=1000),
    entity_type: str | None = Query(
        default=None, pattern=r"^(atom|molecule|organism)$"
    ),
):
    """Get recent lineage activity across all entities."""
    tracker = get_lineage_tracker()
    entries = tracker.get_recent_activity(limit=limit, entity_type=entity_type)
    return {
        "recent_activity": [entry.__dict__ for entry in entries],
        "total": len(entries),
    }


@router.get("/stats")
async def get_lineage_stats():
    """Get lineage statistics."""
    tracker = get_lineage_tracker()
    return tracker.get_stats()
