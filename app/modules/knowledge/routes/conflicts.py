"""Conflict resolution API routes — thin routers delegating to common_lib.

Endpoints: list conflicts, get stats, get by id, resolve, dismiss,
propagate, scan for new conflicts.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.data_storage.database.repository import NotFoundError
from common_lib.modules.knowledge_engine.knowledge_hub.models import ConflictRecord

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Knowledge Conflicts"])


# ── Lazy service ─────────────────────────────────────────────


_conflict_service_instance: Optional[Any] = None


def _get_conflict_service() -> Any:
    global _conflict_service_instance
    if _conflict_service_instance is None:
        from common_lib.modules.knowledge_engine.knowledge_hub.services.conflict_service import (
            KBConflictService,
        )

        _conflict_service_instance = KBConflictService()
    return _conflict_service_instance


# ── Schemas ──────────────────────────────────────────────────


class ConflictResolveRequest(BaseModel):
    winner_chunk_id: str = Field(..., description="UUID of the winning chunk")
    rationale: str = Field("", description="Resolution rationale")
    resolved_by: str = Field("system")
    strategy: str = Field("human_arbitration")
    force: bool = Field(False, description="Override critical domain escalation")


class ConflictDismissRequest(BaseModel):
    reason: str = Field("")
    dismissed_by: str = Field("system")


class ConflictPropagateRequest(BaseModel):
    target_chunk_ids: Optional[list[str]] = Field(
        None, description="Specific chunks to propagate to"
    )
    propagated_by: str = Field("system")


# ── Helper ───────────────────────────────────────────────────


def _conflict_to_dict(rec: ConflictRecord) -> dict[str, Any]:
    return {
        "id": rec.id,
        "chunk_a_id": rec.chunk_a_id,
        "chunk_b_id": rec.chunk_b_id,
        "conflict_type": rec.conflict_type,
        "severity": rec.severity,
        "domain": rec.domain,
        "status": rec.status,
        "chunk_a_content_preview": rec.chunk_a_content_preview,
        "chunk_b_content_preview": rec.chunk_b_content_preview,
        "chunk_a_source": rec.chunk_a_source,
        "chunk_b_source": rec.chunk_b_source,
        "chunk_a_confidence": rec.chunk_a_confidence,
        "chunk_b_confidence": rec.chunk_b_confidence,
        "similarity_score": rec.similarity_score,
        "resolution_strategy": rec.resolution_strategy,
        "winner_chunk_id": rec.winner_chunk_id,
        "loser_chunk_id": rec.loser_chunk_id,
        "rationale": rec.rationale,
        "resolved_by": rec.resolved_by,
        "resolved_at": rec.resolved_at.isoformat() if rec.resolved_at else None,
        "propagated_to": rec.propagated_to or [],
        "detected_at": rec.detected_at.isoformat()
        if isinstance(rec.detected_at, datetime)
        else rec.detected_at,
        "updated_at": rec.updated_at.isoformat()
        if isinstance(rec.updated_at, datetime)
        else rec.updated_at,
    }


# ── Endpoints ────────────────────────────────────────────────


@router.get("/conflicts")
async def list_conflicts(
    status: Optional[str] = Query(
        None, description="Filter by status: open, resolved, dismissed, escalated"
    ),
    severity: Optional[str] = Query(
        None, description="Filter by severity: critical, high, medium, low"
    ),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    source_id: Optional[str] = Query(None, description="Filter by chunk source"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    refresh: bool = Query(False, description="Re-scan chunks for new conflicts"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if refresh:
        svc = _get_conflict_service()
        svc.scan_all(session=session, source_id=source_id)

    from common_lib.modules.data_storage.database.repository import BaseRepository

    _conflict_repo = BaseRepository(ConflictRecord)

    filters: list = []
    if status:
        filters.append(ConflictRecord.status == status)
    if severity:
        filters.append(ConflictRecord.severity == severity)
    if domain:
        filters.append(ConflictRecord.domain == domain)
    if source_id:
        filters.append(
            (ConflictRecord.chunk_a_source == source_id)
            | (ConflictRecord.chunk_b_source == source_id)
        )

    conflicts, total = _conflict_repo.paginated_query(
        session=session,
        filters=filters or None,
        offset=offset,
        limit=limit,
        order_by=ConflictRecord.detected_at.desc(),
    )
    return {
        "success": True,
        "data": {
            "conflicts": [_conflict_to_dict(c) for c in conflicts],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
        "message": f"Found {total} conflicts",
    }


@router.get("/conflicts/stats")
async def get_conflict_stats(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    svc = _get_conflict_service()
    stats = svc.get_stats(session=session)
    return {
        "success": True,
        "data": stats,
        "message": f"{stats['total']} total conflicts",
    }


@router.get("/conflicts/{conflict_id}")
async def get_conflict(
    conflict_id: str = Path(..., description="Conflict UUID"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    from common_lib.modules.data_storage.database.repository import BaseRepository

    _conflict_repo = BaseRepository(ConflictRecord)
    try:
        conflict = _conflict_repo.get_or_raise(
            session, conflict_id, detail=f"Conflict {conflict_id} not found"
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "success": True,
        "data": _conflict_to_dict(conflict),
        "message": "Conflict retrieved",
    }


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    request: ConflictResolveRequest,
    conflict_id: str = Path(..., description="Conflict UUID to resolve"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        svc = _get_conflict_service()
        conflict = svc.resolve(
            session=session,
            conflict_id=conflict_id,
            winner_chunk_id=request.winner_chunk_id,
            rationale=request.rationale,
            resolved_by=request.resolved_by,
            strategy=request.strategy,
            force=request.force,
        )
        return {
            "success": True,
            "data": _conflict_to_dict(conflict),
            "message": f"Conflict resolved via {request.strategy}",
        }
    except Exception as e:
        logger.exception("Conflict resolution failed")
        raise HTTPException(
            status_code=400 if "already" in str(e) or "must be" in str(e) else 500,
            detail=str(e),
        )


@router.post("/conflicts/{conflict_id}/dismiss")
async def dismiss_conflict(
    request: ConflictDismissRequest,
    conflict_id: str = Path(..., description="Conflict UUID to dismiss"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        svc = _get_conflict_service()
        conflict = svc.dismiss(
            session=session,
            conflict_id=conflict_id,
            reason=request.reason,
            dismissed_by=request.dismissed_by,
        )
        return {
            "success": True,
            "data": _conflict_to_dict(conflict),
            "message": "Conflict dismissed",
        }
    except Exception as e:
        logger.exception("Conflict dismissal failed")
        raise HTTPException(
            status_code=400 if "already" in str(e) else 500, detail=str(e)
        )


@router.post("/conflicts/{conflict_id}/propagate")
async def propagate_conflict(
    request: ConflictPropagateRequest,
    conflict_id: str = Path(..., description="Resolved conflict UUID"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        svc = _get_conflict_service()
        conflict = svc.propagate(
            session=session,
            conflict_id=conflict_id,
            target_chunk_ids=request.target_chunk_ids,
            propagated_by=request.propagated_by,
        )
        return {
            "success": True,
            "data": _conflict_to_dict(conflict),
            "message": f"Resolution propagated to {len(conflict.propagated_to)} chunks",
        }
    except Exception as e:
        logger.exception("Conflict propagation failed")
        raise HTTPException(
            status_code=400 if "unresolved" in str(e) else 500, detail=str(e)
        )


@router.post("/conflicts/scan")
async def scan_for_conflicts(
    source_id: Optional[str] = Query(
        None, description="Scan only chunks from this source"
    ),
    limit: int = Query(500, ge=1, le=2000),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    svc = _get_conflict_service()
    new_conflicts = svc.scan_all(session=session, limit=limit, source_id=source_id)
    return {
        "success": True,
        "data": {
            "new_conflicts": [_conflict_to_dict(c) for c in new_conflicts],
            "count": len(new_conflicts),
        },
        "message": f"Scanned for conflicts: {len(new_conflicts)} detected",
    }


__all__ = ["router"]
