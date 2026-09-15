"""Thin batch routes — submit/status/cancel + generation-history parity (C078).

All routes delegate to common_lib batch_queue. No business logic here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from common_lib.modules.audio_processing.memory.feature_flags import (
    BATCH_ENABLED,
    is_enabled,
)

router = APIRouter(prefix="/batch", tags=["Audio — Batch"])


class BatchSubmitRequest(BaseModel):
    job_type: str = Field(
        ..., description="Type of job (e.g. 'tts_batch', 'transcribe_batch')"
    )
    payload: dict = Field(default_factory=dict, description="Job input payload")
    priority: str = Field(
        default="NORMAL", description="Job priority: LOW, NORMAL, HIGH, CRITICAL"
    )
    tenant_id: str | None = Field(default=None, description="Optional tenant id")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry attempts")
    metadata: dict = Field(default_factory=dict, description="Optional metadata")


class BatchSubmitResponse(BaseModel):
    job_id: str


class BatchJobResponse(BaseModel):
    job_id: str
    job_type: str
    payload: dict
    status: str
    priority: int
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    progress: float = 0.0
    result: dict | None = None
    error: str | None = None
    metadata: dict = Field(default_factory=dict)
    tenant_id: str | None = None
    max_retries: int = 3
    retry_count: int = 0


class BatchListResponse(BaseModel):
    jobs: list[BatchJobResponse]
    total: int
    limit: int
    offset: int


@router.post("/submit", response_model=BatchSubmitResponse)
async def submit_batch_job(request: BatchSubmitRequest) -> BatchSubmitResponse:
    """Submit a new batch job for async processing."""
    if not is_enabled(BATCH_ENABLED):
        raise HTTPException(status_code=403, detail="Batch processing is disabled")

    from common_lib.modules.audio_processing.library.batch_queue import (
        get_batch_queue,
        JobPriority,
    )

    queue = get_batch_queue()
    priority_enum = (
        JobPriority[request.priority.upper()]
        if isinstance(request.priority, str)
        else request.priority
    )

    job_id = await queue.enqueue(
        job_type=request.job_type,
        payload=request.payload,
        priority=priority_enum,
        tenant_id=request.tenant_id,
        max_retries=request.max_retries,
        metadata=request.metadata,
    )
    return BatchSubmitResponse(job_id=job_id)


@router.get("/{job_id}", response_model=BatchJobResponse)
async def get_batch_job(job_id: str) -> BatchJobResponse:
    """Get batch job status and result."""
    if not is_enabled(BATCH_ENABLED):
        raise HTTPException(status_code=403, detail="Batch processing is disabled")

    from common_lib.modules.audio_processing.library.batch_queue import get_batch_queue

    queue = get_batch_queue()
    job = await queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return BatchJobResponse(**job)


@router.post("/{job_id}/cancel")
async def cancel_batch_job(job_id: str) -> dict:
    """Cancel a pending or running batch job."""
    if not is_enabled(BATCH_ENABLED):
        raise HTTPException(status_code=403, detail="Batch processing is disabled")

    from common_lib.modules.audio_processing.library.batch_queue import get_batch_queue

    queue = get_batch_queue()
    cancelled = await queue.cancel(job_id)
    if not cancelled:
        job = await queue.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(
            status_code=409, detail="Job cannot be cancelled (already terminal)"
        )
    return {"cancelled": True, "job_id": job_id}


@router.get("", response_model=BatchListResponse)
async def list_batch_jobs(
    status: str | None = Query(default=None, description="Filter by status"),
    tenant_id: str | None = Query(default=None, description="Filter by tenant"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> BatchListResponse:
    """List batch jobs with filtering and pagination."""
    if not is_enabled(BATCH_ENABLED):
        raise HTTPException(status_code=403, detail="Batch processing is disabled")

    from common_lib.modules.audio_processing.library.batch_queue import (
        get_batch_queue,
        JobStatus,
    )

    queue = get_batch_queue()
    status_enum = JobStatus[status.upper()] if status else None

    result = await queue.list_jobs(
        status=status_enum,
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )
    return BatchListResponse(
        jobs=[BatchJobResponse(**j) for j in result["jobs"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


@router.get("/history/generation", response_model=BatchListResponse)
async def generation_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> BatchListResponse:
    """Generation history parity — filter batch jobs of type 'tts_batch' or 'speak_batch'."""
    if not is_enabled(BATCH_ENABLED):
        raise HTTPException(status_code=403, detail="Batch processing is disabled")

    from common_lib.modules.audio_processing.library.batch_queue import get_batch_queue

    queue = get_batch_queue()
    result = await queue.list_jobs(
        tenant_id=None,
        limit=limit,
        offset=offset,
    )
    # Filter to generation job types
    gen_jobs = [
        j for j in result["jobs"] if j["job_type"] in ("tts_batch", "speak_batch")
    ]
    return BatchListResponse(
        jobs=[BatchJobResponse(**j) for j in gen_jobs],
        total=len(gen_jobs),
        limit=limit,
        offset=offset,
    )
