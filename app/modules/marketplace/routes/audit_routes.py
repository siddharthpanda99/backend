"""Entity audit + versioning API endpoints.

Thin router layer — delegates to EntityAuditAdapter.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common_lib_integration import common_memory
from common_lib.modules.integration.adapters.entity_audit_adapter import (
    EntityAuditAdapter,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Entity Audit"])


async def get_db_session() -> AsyncSession:
    """Get database session from common_memory (SQLAlchemyMemoryStore)."""
    # common_memory is a SQLAlchemyMemoryStore with async session support
    async with common_memory.get_session() as session:
        yield session


def _get_adapter():
    """Lazy adapter getter."""

    async def _dep():
        async for session in get_db_session():
            yield EntityAuditAdapter(session)

    return _dep


_audit_dep = Depends(_get_adapter())


# ── Audit Log ───────────────────────────────────────────────────────


@router.get("/{entity_type}/{entity_id}/audit")
async def get_entity_audit_history(
    entity_type: str,
    entity_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    adapter: EntityAuditAdapter = _audit_dep,
):
    """Get audit history for any entity."""
    history = await adapter.get_entity_history(entity_type, entity_id, limit, offset)
    total = await adapter.get_entity_history_count(entity_type, entity_id)
    return {"status": "ok", "entries": history, "total": total}


@router.post("/{entity_type}/{entity_id}/audit")
async def log_entity_action(
    entity_type: str,
    entity_id: str,
    action: str = Query(
        ..., description="created|updated|deleted|restored|published|archived"
    ),
    entity_name: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    actor_name: Optional[str] = Query(None),
    version_number: Optional[int] = Query(None),
    adapter: EntityAuditAdapter = _audit_dep,
):
    """Log an action on an entity (called by services on CRUD)."""
    entry = await adapter.log_action(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        entity_name=entity_name,
        actor_id=actor_id,
        actor_name=actor_name,
        version_number=version_number,
    )
    return {"status": "ok", "entry_id": entry.id}


@router.get("/audit/search")
async def search_audit_log(
    entity_type: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    after: Optional[datetime] = Query(None),
    before: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    adapter: EntityAuditAdapter = _audit_dep,
):
    """Search audit log with filters."""
    entries = await adapter.search_audit_log(
        entity_type=entity_type,
        actor_id=actor_id,
        action=action,
        after=after,
        before=before,
        limit=limit,
        offset=offset,
    )
    return {"status": "ok", "entries": entries, "count": len(entries)}


# ── Version Snapshots ───────────────────────────────────────────────


@router.get("/{entity_type}/{entity_id}/versions")
async def get_entity_versions(
    entity_type: str,
    entity_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    adapter: EntityAuditAdapter = _audit_dep,
):
    """Get all versions of an entity."""
    versions = await adapter.get_versions(entity_type, entity_id, limit, offset)
    total = await adapter.get_version_count(entity_type, entity_id)
    return {"status": "ok", "versions": versions, "total": total}


@router.get("/{entity_type}/{entity_id}/versions/{version_number}")
async def get_entity_version(
    entity_type: str,
    entity_id: str,
    version_number: int,
    adapter: EntityAuditAdapter = _audit_dep,
):
    """Get a specific version snapshot (full entity state)."""
    version = await adapter.get_version(entity_type, entity_id, version_number)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"status": "ok", "version": version}


@router.get("/{entity_type}/{entity_id}/versions/latest")
async def get_latest_version(
    entity_type: str,
    entity_id: str,
    adapter: EntityAuditAdapter = _audit_dep,
):
    """Get the latest version snapshot."""
    version = await adapter.get_latest_version(entity_type, entity_id)
    if not version:
        raise HTTPException(status_code=404, detail="No versions found")
    return {"status": "ok", "version": version}


@router.post("/{entity_type}/{entity_id}/versions")
async def create_version_snapshot(
    entity_type: str,
    entity_id: str,
    snapshot: dict,
    author: Optional[str] = Query(None),
    author_id: Optional[str] = Query(None),
    message: Optional[str] = Query(None),
    adapter: EntityAuditAdapter = _audit_dep,
):
    """Create a new version snapshot (called by services on save)."""
    version = await adapter.create_version(
        entity_type=entity_type,
        entity_id=entity_id,
        snapshot=snapshot,
        author=author,
        author_id=author_id,
        message=message,
    )
    return {"status": "ok", "version_number": version.version_number}
