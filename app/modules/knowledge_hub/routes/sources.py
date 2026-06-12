"""
Knowledge Hub — Source Routes.

Endpoints:
    Source Types:
        GET    /knowledge-hub/source-types           — List all source types
        POST   /knowledge-hub/source-types           — Create source type
        GET    /knowledge-hub/source-types/{id}      — Get source type
        PUT    /knowledge-hub/source-types/{id}      — Update source type
        DELETE /knowledge-hub/source-types/{id}      — Delete source type

    Source Configs:
        GET    /knowledge-hub/sources                — List source configs
        POST   /knowledge-hub/sources                — Create source config
        GET    /knowledge-hub/sources/{id}           — Get source config
        PUT    /knowledge-hub/sources/{id}           — Update source config
        DELETE /knowledge-hub/sources/{id}           — Delete source config
        POST   /knowledge-hub/sources/{id}/execute   — Execute/test source
        POST   /knowledge-hub/sources/{id}/verify    — Verify source
        GET    /knowledge-hub/sources/{id}/preview   — Preview source data
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.knowledge_hub.models import (
    SourceConfigRecord,
    SourceTypeRecord,
)
from common_lib.modules.knowledge_hub.services.source_service import (
    SourceService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-hub", tags=["Knowledge Hub — Sources"])


# ── Pydantic Schemas ───────────────────────────────────────────────


class SourceTypeCreate(BaseModel):
    id: str = Field(..., description="Unique slug e.g. 'arxiv_api'")
    name: str = Field(..., description="Human-readable name")
    description: Optional[str] = None
    icon: Optional[str] = None
    category: str = Field(default="api")
    config_schema: Dict[str, Any] = Field(default_factory=dict)


class SourceTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    category: Optional[str] = None
    config_schema: Optional[Dict[str, Any]] = None


class SourceConfigCreate(BaseModel):
    id: Optional[str] = None
    source_type_id: str = Field(..., description="FK to SourceTypeRecord")
    name: str = Field(..., description="User-given name")
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class SourceConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    tags: Optional[list[str]] = None


# ═══════════════════════════════════════════════════════════════════
# Source Types
# ═══════════════════════════════════════════════════════════════════


@router.get("/source-types")
def list_source_types(
    category: Optional[str] = Query(None, description="Filter by category"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List all source type definitions."""
    types = SourceService.list_source_types(session, category=category)
    return {
        "success": True,
        "data": [_type_to_dict(t) for t in types],
        "total": len(types),
    }


@router.get("/source-types/{type_id}")
def get_source_type(
    type_id: str = Path(..., description="Source type ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get a source type definition by ID."""
    record = SourceService.get_source_type(session, type_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Source type '{type_id}' not found")
    return {"success": True, "data": _type_to_dict(record)}


@router.post("/source-types", status_code=201)
def create_source_type(
    request: SourceTypeCreate,
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Create a new source type definition."""
    record = SourceService.create_source_type(session, request.model_dump())
    return {"success": True, "data": _type_to_dict(record)}


@router.put("/source-types/{type_id}")
def update_source_type(
    request: SourceTypeUpdate,
    type_id: str = Path(..., description="Source type ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Update an existing source type definition."""
    record = SourceService.update_source_type(
        session, type_id, request.model_dump(exclude_none=True)
    )
    if not record:
        raise HTTPException(status_code=404, detail=f"Source type '{type_id}' not found")
    return {"success": True, "data": _type_to_dict(record)}


@router.delete("/source-types/{type_id}")
def delete_source_type(
    type_id: str = Path(..., description="Source type ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Delete a source type definition."""
    deleted = SourceService.delete_source_type(session, type_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Source type '{type_id}' not found")
    return {"success": True, "message": f"Source type '{type_id}' deleted"}


# ═══════════════════════════════════════════════════════════════════
# Source Configs
# ═══════════════════════════════════════════════════════════════════


@router.get("/sources")
def list_source_configs(
    source_type_id: Optional[str] = Query(None, description="Filter by source type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List source configurations."""
    configs = SourceService.list_source_configs(
        session, source_type_id=source_type_id, status=status
    )
    return {
        "success": True,
        "data": [_config_to_dict(c) for c in configs],
        "total": len(configs),
    }


@router.get("/sources/{config_id}")
def get_source_config(
    config_id: str = Path(..., description="Source config ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get a source configuration by ID."""
    record = SourceService.get_source_config(session, config_id)
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Source config '{config_id}' not found"
        )
    return {"success": True, "data": _config_to_dict(record)}


@router.post("/sources", status_code=201)
def create_source_config(
    request: SourceConfigCreate,
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Create a new source configuration."""
    record = SourceService.create_source_config(session, request.model_dump())
    return {"success": True, "data": _config_to_dict(record)}


@router.put("/sources/{config_id}")
def update_source_config(
    request: SourceConfigUpdate,
    config_id: str = Path(..., description="Source config ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Update an existing source configuration."""
    record = SourceService.update_source_config(
        session, config_id, request.model_dump(exclude_none=True)
    )
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Source config '{config_id}' not found"
        )
    return {"success": True, "data": _config_to_dict(record)}


@router.delete("/sources/{config_id}")
def delete_source_config(
    config_id: str = Path(..., description="Source config ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Delete a source configuration."""
    deleted = SourceService.delete_source_config(session, config_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Source config '{config_id}' not found"
        )
    return {"success": True, "message": f"Source config '{config_id}' deleted"}


# ═══════════════════════════════════════════════════════════════════
# Execute / Verify / Preview
# ═══════════════════════════════════════════════════════════════════


@router.post("/sources/{config_id}/execute")
def execute_source(
    config_id: str = Path(..., description="Source config ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Execute/test a source connection.

    Returns sample data and execution status. Use this to verify
    data extraction is working before marking as verified.
    """
    result = SourceService.execute_source(session, config_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.post("/sources/{config_id}/verify")
def verify_source(
    config_id: str = Path(..., description="Source config ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Mark a source configuration as verified.

    Only verified sources can be used in production packets.
    Should be called after successful execution.
    """
    record = SourceService.verify_source(session, config_id)
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Source config '{config_id}' not found"
        )
    return {
        "success": True,
        "data": _config_to_dict(record),
        "message": f"Source '{record.name}' verified successfully",
    }


@router.get("/sources/{config_id}/preview")
def preview_source(
    config_id: str = Path(..., description="Source config ID"),
    limit: int = Query(10, ge=1, le=100),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get a preview of data from a source."""
    result = SourceService.get_source_preview(session, config_id, limit=limit)
    if not result.get("success"):
        raise HTTPException(
            status_code=404, detail=f"Source config '{config_id}' not found"
        )
    return result


# ── Serialization helpers ─────────────────────────────────────


def _type_to_dict(record: SourceTypeRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "description": record.description,
        "icon": record.icon,
        "category": record.category,
        "config_schema": record.config_schema,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _config_to_dict(record: SourceConfigRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "source_type_id": record.source_type_id,
        "name": record.name,
        "description": record.description,
        "config": record.config,
        "status": record.status,
        "verified_at": record.verified_at.isoformat() if record.verified_at else None,
        "verified_by": record.verified_by,
        "tags": record.tags,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
