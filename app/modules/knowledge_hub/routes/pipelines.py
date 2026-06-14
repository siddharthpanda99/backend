"""
Knowledge Hub — Ingestion Pipeline Routes.

Endpoints:
    GET    /knowledge-hub/pipelines                    — List pipelines
    POST   /knowledge-hub/pipelines                    — Create pipeline
    GET    /knowledge-hub/pipelines/{id}               — Get pipeline
    PUT    /knowledge-hub/pipelines/{id}               — Update pipeline
    DELETE /knowledge-hub/pipelines/{id}               — Delete pipeline
    POST   /knowledge-hub/pipelines/{id}/execute       — Execute pipeline
    POST   /knowledge-hub/pipelines/{id}/verify        — Verify pipeline
    POST   /knowledge-hub/pipelines/validate           — Validate pipeline definition
    GET    /knowledge-hub/pipelines/{id}/jobs          — List jobs for pipeline
    GET    /knowledge-hub/pipelines/{id}/jobs/{job_id} — Get job details
    POST   /knowledge-hub/pipelines/{id}/jobs/{job_id}/cancel  — Cancel job
    POST   /knowledge-hub/pipelines/{id}/jobs/{job_id}/retry   — Retry job
    GET    /knowledge-hub/pipelines/{id}/jobs/{job_id}/logs    — Get job logs
    GET    /knowledge-hub/pipelines/{id}/jobs/{job_id}/progress — SSE job progress
    GET    /knowledge-hub/feature-flags                — List feature flags
    PUT    /knowledge-hub/feature-flags/{flag}         — Toggle feature flag
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.knowledge_hub.models import IngestionPipelineRecord
from common_lib.modules.knowledge_hub.services.ingestion_service import (
    IngestionService,
    PipelineJobService,
    _job_to_dict,
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


class FeatureFlagToggle(BaseModel):
    enabled: bool = Field(..., description="Whether the feature flag is enabled")


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
    records processed per step, chunks stored, and embeddings generated.
    Creates a PipelineJobRecord for progress tracking.
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


# ═══════════════════════════════════════════════════════════════════
# Pipeline Job Management (Phase 9 — Pipeline Monitor)
# ═══════════════════════════════════════════════════════════════════


@router.get("/pipelines/{pipeline_id}/jobs")
def list_pipeline_jobs(
    pipeline_id: str = Path(..., description="Pipeline ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List execution jobs for a pipeline."""
    jobs = PipelineJobService.list_jobs(
        session, pipeline_id=pipeline_id, status=status, limit=limit, offset=offset
    )
    return {
        "success": True,
        "data": [_job_to_dict(j) for j in jobs],
        "total": len(jobs),
    }


@router.get("/pipelines/{pipeline_id}/jobs/{job_id}")
def get_pipeline_job(
    pipeline_id: str = Path(..., description="Pipeline ID"),
    job_id: str = Path(..., description="Job ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get a single pipeline execution job."""
    job = PipelineJobService.get_job(session, job_id)
    if not job or job.pipeline_id != pipeline_id:
        raise HTTPException(
            status_code=404, detail=f"Job '{job_id}' not found for pipeline '{pipeline_id}'"
        )
    return {"success": True, "data": _job_to_dict(job)}


@router.post("/pipelines/{pipeline_id}/jobs/{job_id}/cancel")
def cancel_pipeline_job(
    pipeline_id: str = Path(..., description="Pipeline ID"),
    job_id: str = Path(..., description="Job ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Cancel a running or pending pipeline job."""
    job = PipelineJobService.get_job(session, job_id)
    if not job or job.pipeline_id != pipeline_id:
        raise HTTPException(
            status_code=404, detail=f"Job '{job_id}' not found for pipeline '{pipeline_id}'"
        )
    cancelled = PipelineJobService.cancel_job(session, job_id)
    if cancelled is None:
        raise HTTPException(
            status_code=400,
            detail=f"Job '{job_id}' is in status '{job.status}' and cannot be cancelled. Only 'pending' or 'running' jobs can be cancelled.",
        )
    return {
        "success": True,
        "data": _job_to_dict(cancelled),
        "message": f"Job '{job_id}' cancelled",
    }


@router.post("/pipelines/{pipeline_id}/jobs/{job_id}/retry")
def retry_pipeline_job(
    pipeline_id: str = Path(..., description="Pipeline ID"),
    job_id: str = Path(..., description="Job ID to retry"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Retry a failed or cancelled pipeline job.

    Creates a new execution job for the same pipeline.
    """
    job = PipelineJobService.get_job(session, job_id)
    if not job or job.pipeline_id != pipeline_id:
        raise HTTPException(
            status_code=404, detail=f"Job '{job_id}' not found for pipeline '{pipeline_id}'"
        )
    new_job = PipelineJobService.retry_job(session, job_id)
    if new_job is None:
        raise HTTPException(
            status_code=400,
            detail=f"Job '{job_id}' is in status '{job.status}' and cannot be retried. Only 'failed' or 'cancelled' jobs can be retried.",
        )
    return {
        "success": True,
        "data": _job_to_dict(new_job),
        "message": f"Retry created new job '{new_job.id}' for pipeline '{pipeline_id}'",
    }


@router.get("/pipelines/{pipeline_id}/jobs/{job_id}/logs")
def get_pipeline_job_logs(
    pipeline_id: str = Path(..., description="Pipeline ID"),
    job_id: str = Path(..., description="Job ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get the execution log for a pipeline job."""
    job = PipelineJobService.get_job(session, job_id)
    if not job or job.pipeline_id != pipeline_id:
        raise HTTPException(
            status_code=404, detail=f"Job '{job_id}' not found for pipeline '{pipeline_id}'"
        )
    logs = PipelineJobService.get_job_logs(session, job_id)
    return {"success": True, "data": logs}


@router.get("/pipelines/{pipeline_id}/jobs/{job_id}/progress")
async def stream_pipeline_job_progress(
    pipeline_id: str = Path(..., description="Pipeline ID"),
    job_id: str = Path(..., description="Job ID"),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Stream pipeline job progress as SSE events."""
    job = PipelineJobService.get_job(session, job_id)
    if not job or job.pipeline_id != pipeline_id:
        raise HTTPException(
            status_code=404, detail=f"Job '{job_id}' not found for pipeline '{pipeline_id}'"
        )

    async def event_stream():
        for _ in range(60):  # Max 60 polls (60 seconds)
            current = PipelineJobService.get_job_progress(session, job_id)
            if current is None:
                yield f"event: error\ndata: {json.dumps({'message': 'Job not found'})}\n\n"
                return

            yield f"event: progress\ndata: {json.dumps(current)}\n\n"

            if current["status"] in ("completed", "failed", "cancelled"):
                yield f"event: done\ndata: {json.dumps({'status': current['status']})}\n\n"
                return

            import asyncio
            await asyncio.sleep(1)

        yield f"event: timeout\ndata: {json.dumps({'message': 'Progress polling timed out'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════════════════════════════
# Feature Flags (Phase 9 — Pipeline Monitor)
# ═══════════════════════════════════════════════════════════════════


# In-memory feature flags — persisted across requests within the process
_FEATURE_FLAGS: Dict[str, bool] = {
    "pipeline_auto_retry": True,
    "job_progress_notifications": True,
    "cancel_job_enabled": True,
    "retry_job_enabled": True,
    "job_logs_enabled": True,
    "sse_progress_enabled": True,
}


@router.get("/feature-flags")
def list_feature_flags() -> Dict[str, Any]:
    """List all feature flags with their current state."""
    return {
        "success": True,
        "data": _FEATURE_FLAGS,
        "total": len(_FEATURE_FLAGS),
    }


@router.put("/feature-flags/{flag}")
def toggle_feature_flag(
    flag: str = Path(..., description="Feature flag name"),
    enabled: bool = Query(True, description="Whether the flag is enabled"),
) -> Dict[str, Any]:
    """Toggle a feature flag on or off."""
    if flag not in _FEATURE_FLAGS:
        raise HTTPException(
            status_code=404,
            detail=f"Feature flag '{flag}' not found. Available: {list(_FEATURE_FLAGS.keys())}",
        )
    _FEATURE_FLAGS[flag] = enabled
    return {
        "success": True,
        "data": {flag: _FEATURE_FLAGS[flag]},
        "message": f"Feature flag '{flag}' set to {_FEATURE_FLAGS[flag]}",
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
