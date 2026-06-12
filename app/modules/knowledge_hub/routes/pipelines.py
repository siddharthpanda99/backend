"""
Knowledge Hub — Ingestion Pipeline Routes.

Endpoints:
    GET    /knowledge-hub/pipelines                — List pipelines
    POST   /knowledge-hub/pipelines                — Create pipeline
    GET    /knowledge-hub/pipelines/{id}           — Get pipeline
    PUT    /knowledge-hub/pipelines/{id}           — Update pipeline
    DELETE /knowledge-hub/pipelines/{id}           — Delete pipeline
    POST   /knowledge-hub/pipelines/{id}/execute   — Execute pipeline
    POST   /knowledge-hub/pipelines/{id}/verify    — Verify pipeline
    POST   /knowledge-hub/pipelines/validate       — Validate pipeline definition
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.knowledge_hub.models import IngestionPipelineRecord
from common_lib.modules.knowledge_hub.services.ingestion_service import (
    IngestionService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-hub", tags=["Knowledge Hub — Ingestion"])


# ── Pydantic Schemas ───────────────────────────────────────────────


class PipelineCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., description="Pipeline name")
    description: Optional[str] = None
    source_config_id: str = Field(..., description="FK to SourceConfigRecord")
    pipeline_definition: Dict[str, Any] = Field(
        ..., description="YAML/JSON workflow definition"
    )


class PipelineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_config_id: Optional[str] = None
    pipeline_definition: Optional[Dict[str, Any]] = None


class PipelineValidateRequest(BaseModel):
    pipeline_definition: Dict[str, Any] = Field(
        ..., description="YAML/JSON workflow definition to validate"
    )


# ═══════════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("/pipelines")
def list_pipelines(
    source_config_id: Optional[str] = Query(None, description="Filter by source config"),
    status: Optional[str] = Query(None, description="Filter by status"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List ingestion pipelines."""
    pipelines = IngestionService.list_pipelines(
        session, source_config_id=source_config_id, status=status
    )
    return {
        "success": True,
        "data": [_pipeline_to_dict(p) for p in pipelines],
        "total": len(pipelines),
    }


@router.get("/pipelines/{pipeline_id}")
def get_pipeline(
    pipeline_id: str = Path(..., description="Pipeline ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get an ingestion pipeline by ID."""
    record = IngestionService.get_pipeline(session, pipeline_id)
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Pipeline '{pipeline_id}' not found"
        )
    return {"success": True, "data": _pipeline_to_dict(record)}


@router.post("/pipelines", status_code=201)
def create_pipeline(
    request: PipelineCreate,
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Create a new ingestion pipeline."""
    record = IngestionService.create_pipeline(session, request.model_dump())
    return {"success": True, "data": _pipeline_to_dict(record)}


@router.put("/pipelines/{pipeline_id}")
def update_pipeline(
    request: PipelineUpdate,
    pipeline_id: str = Path(..., description="Pipeline ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Update an existing ingestion pipeline."""
    record = IngestionService.update_pipeline(
        session, pipeline_id, request.model_dump(exclude_none=True)
    )
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Pipeline '{pipeline_id}' not found"
        )
    return {"success": True, "data": _pipeline_to_dict(record)}


@router.delete("/pipelines/{pipeline_id}")
def delete_pipeline(
    pipeline_id: str = Path(..., description="Pipeline ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Delete an ingestion pipeline."""
    deleted = IngestionService.delete_pipeline(session, pipeline_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Pipeline '{pipeline_id}' not found"
        )
    return {"success": True, "message": f"Pipeline '{pipeline_id}' deleted"}


# ═══════════════════════════════════════════════════════════════════
# Validate / Execute / Verify
# ═══════════════════════════════════════════════════════════════════


@router.post("/pipelines/validate")
def validate_pipeline_definition(
    request: PipelineValidateRequest,
) -> Dict[str, Any]:
    """Validate a pipeline YAML/JSON definition without saving.

    Checks for required fields, valid operations, and structural
    correctness. Returns validation errors and warnings.
    """
    result = IngestionService.validate_pipeline_definition(
        request.pipeline_definition
    )
    return {
        "success": True,
        "data": result,
    }


@router.post("/pipelines/{pipeline_id}/execute")
def execute_pipeline(
    pipeline_id: str = Path(..., description="Pipeline ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Execute an ingestion pipeline.

    Runs all pipeline steps and returns execution results including
    records processed per step and total execution time.
    """
    result = IngestionService.execute_pipeline(session, pipeline_id)
    if not result.get("success"):
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.post("/pipelines/{pipeline_id}/verify")
def verify_pipeline(
    pipeline_id: str = Path(..., description="Pipeline ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Mark an ingestion pipeline as verified.

    Should be called after successful execution to confirm the
    pipeline produces correct results.
    """
    record = IngestionService.verify_pipeline(session, pipeline_id)
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Pipeline '{pipeline_id}' not found"
        )
    return {
        "success": True,
        "data": _pipeline_to_dict(record),
        "message": f"Pipeline '{record.name}' verified successfully",
    }


# ── Serialization helpers ─────────────────────────────────────


def _pipeline_to_dict(record: IngestionPipelineRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "description": record.description,
        "source_config_id": record.source_config_id,
        "pipeline_definition": record.pipeline_definition,
        "status": record.status,
        "verified_at": record.verified_at.isoformat() if record.verified_at else None,
        "verified_by": record.verified_by,
        "last_executed_at": (
            record.last_executed_at.isoformat() if record.last_executed_at else None
        ),
        "last_execution_result": record.last_execution_result,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
