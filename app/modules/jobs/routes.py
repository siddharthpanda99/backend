"""Background jobs API — thin router delegating to common_lib JobService.

Mounted at ``/api/v1/jobs``. All business logic lives in
``common_lib.modules.jobs``; this file only maps HTTP to service calls.
The service is fully synchronous and fast (in-memory snapshots), so these
handlers are plain ``def`` — nothing long-running is awaited inline.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.jobs.models import JobRecord
from common_lib.modules.jobs.service import get_job_service

router = APIRouter()


class JobCancelResponse(BaseModel):
    job_id: str = Field(description="Cancelled job id")
    status: str = Field(description="Resulting job status")


def _dump(record: JobRecord) -> dict[str, Any]:
    return record.to_dict()


@router.get("/")
def list_jobs(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """List background jobs newest-first with optional filters."""
    records: list[JobRecord] = get_job_service().list(
        user_id=user_id, status=status, kind=kind, limit=limit, offset=offset
    )
    payload: list[dict[str, Any]] = [_dump(r) for r in records]
    return {"data": payload, "total": len(payload)}


@router.get("/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    """Return one job record (status, progress, result_refs, error)."""
    record: JobRecord | None = get_job_service().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {"data": _dump(record)}


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    """Request cooperative cancellation of a queued/running job."""
    record: JobRecord | None = get_job_service().cancel(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    response = JobCancelResponse(job_id=record.id, status=record.status)
    return {"data": response.model_dump()}
