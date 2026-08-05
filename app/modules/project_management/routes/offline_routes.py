"""Offline sync, cache, and conflict resolution REST routes.

Domain 26 — Mobile/Offline.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from common_lib.modules.project_management.offline.service import OfflineSyncService
from common_lib.modules.project_management.offline.models import OfflineMutation

from app.modules.auth.dependencies import get_current_user
from app.modules.project_management.dependencies import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter()


# ===========================================================================
# Mutation Queue Endpoints
# ===========================================================================

@router.post("/offline/mutations")
def enqueue_mutation(
    workspace_id: str,
    entity_type: str,
    entity_id: str,
    mutation_type: str,
    payload: Optional[dict] = None,
    created_by: Optional[str] = None,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Record a pending mutation for offline sync."""
    svc = OfflineSyncService(session=session)
    mut = svc.enqueue_mutation(
        workspace_id=workspace_id,
        entity_type=entity_type,
        entity_id=entity_id,
        mutation_type=mutation_type,
        payload=payload,
        created_by=created_by or current_user.get("id"),
    )
    return {"id": mut.id, "status": mut.status}


@router.get("/offline/mutations")
def get_pending_mutations(
    workspace_id: str,
    since: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """List pending (unsynced) mutations for a workspace."""
    svc = OfflineSyncService(session=session)
    dt = datetime.fromisoformat(since) if since else None
    items = svc.get_pending_mutations(
        workspace_id=workspace_id, since=dt, entity_type=entity_type, limit=limit,
    )
    return {
        "mutations": [m.model_dump() for m in items],
        "count": len(items),
    }


@router.get("/offline/sync-status")
def get_sync_status(
    workspace_id: str,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Get aggregate sync health for a workspace."""
    svc = OfflineSyncService(session=session)
    return svc.get_sync_status(workspace_id=workspace_id)


@router.post("/offline/mutations/{mutation_id}/ack")
def acknowledge_mutation(
    mutation_id: str,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Mark a mutation as successfully synced."""
    svc = OfflineSyncService(session=session)
    success = svc.mark_synced(mutation_id=mutation_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Mutation {mutation_id} not found")
    return {"status": "synced", "mutation_id": mutation_id}


# ===========================================================================
# Edge Cache Endpoints
# ===========================================================================

@router.post("/offline/cache")
def set_cache_entry(
    workspace_id: str,
    cache_key: str,
    entity_type: str,
    entity_id: str,
    data: dict,
    ttl_seconds: int = 300,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Store or update an edge-cache entry."""
    svc = OfflineSyncService(session=session)
    entry = svc.set_cache_entry(
        workspace_id=workspace_id, cache_key=cache_key,
        entity_type=entity_type, entity_id=entity_id,
        data=data, ttl_seconds=ttl_seconds,
    )
    return {"id": entry.id, "cache_key": entry.cache_key, "version": entry.version}


@router.get("/offline/cache/{cache_key}")
def get_cache_entry(
    cache_key: str,
    workspace_id: str = Query(...),
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Retrieve a cached entry by cache_key."""
    svc = OfflineSyncService(session=session)
    entry = svc.get_cache_entry(workspace_id=workspace_id, cache_key=cache_key)
    if not entry:
        raise HTTPException(status_code=404, detail="Cache miss")
    return {"id": entry.id, "cache_key": entry.cache_key, "data": entry.data, "version": entry.version}


@router.delete("/offline/cache")
def invalidate_cache(
    workspace_id: str,
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Invalidate cached entries."""
    svc = OfflineSyncService(session=session)
    count = svc.invalidate_cache(
        workspace_id=workspace_id, entity_type=entity_type, entity_id=entity_id,
    )
    return {"deleted_count": count}


@router.post("/offline/cache/clear-expired")
def clear_expired_cache(
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Remove all expired cache entries."""
    svc = OfflineSyncService(session=session)
    count = svc.clear_expired_cache()
    return {"deleted_count": count}


# ===========================================================================
# Conflict Resolution Endpoints
# ===========================================================================

@router.get("/offline/conflicts")
def list_conflicts(
    workspace_id: str,
    unresolved_only: bool = True,
    limit: int = 50,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """List sync conflict records."""
    svc = OfflineSyncService(session=session)
    items = svc.get_conflicts(
        workspace_id=workspace_id, unresolved_only=unresolved_only, limit=limit,
    )
    return {
        "conflicts": [c.model_dump() for c in items],
        "count": len(items),
    }


@router.post("/offline/conflicts")
def resolve_conflict(
    workspace_id: str,
    entity_type: str,
    entity_id: str,
    local_version: int,
    server_version: int,
    local_payload: Optional[dict] = None,
    server_payload: Optional[dict] = None,
    resolution_strategy: str = "manual",
    resolved_data: Optional[dict] = None,
    resolved_by: Optional[str] = None,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Record a sync conflict resolution."""
    svc = OfflineSyncService(session=session)
    res = svc.resolve_conflict(
        workspace_id=workspace_id,
        entity_type=entity_type,
        entity_id=entity_id,
        local_version=local_version,
        server_version=server_version,
        local_payload=local_payload,
        server_payload=server_payload,
        resolution_strategy=resolution_strategy,
        resolved_data=resolved_data,
        resolved_by=resolved_by or current_user.get("id"),
    )
    return {"id": res.id, "resolution_strategy": res.resolution_strategy}
