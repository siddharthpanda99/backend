"""Background jobs API — thin router delegating to the common_lib JobService.

Mounted at ``/api/v1/jobs``. All business logic lives in
``common_lib.modules.jobs``; this file only maps HTTP to service calls plus the
composition-root wiring that the library is not allowed to do itself:

* **Persistence wiring** — attaches the DB-backed ``JobStore`` (session factory
  injected here, so ``common_lib`` keeps zero knowledge of the DB layer) and
  rehydrates recent records on first use.
* **Progress push** — ``GET /{job_id}/events`` streams SSE status/progress so
  clients do not have to poll.
* **Retention** — ``POST /cleanup`` drops old terminal records.
* **Tenancy** — ``mine=true`` scopes listing to the authenticated identity and
  ``limit`` is capped.

The service is fully synchronous and fast (in-memory snapshots), so handlers are
plain ``def`` — nothing long-running is awaited inline.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated, Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from common_lib.modules.auth.authorization import PlatformIdentity
from common_lib.modules.jobs.models import JobRecord, JobStatus
from common_lib.modules.jobs.service import get_job_service
from common_lib.modules.jobs.store import JobStore

from app.modules.auth.dependencies.authz import get_current_identity

logger = logging.getLogger(__name__)

router = APIRouter()

TERMINAL_STATUSES: tuple[str, ...] = (
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
)
MAX_LIMIT: int = 200
POLL_INTERVAL_SECONDS: float = 0.5
SSE_TIMEOUT_SECONDS: int = 900

_state: dict[str, bool] = {"configured": False, "rehydrated": False}


# ---------------------------------------------------------------------------
# Composition-root wiring
# ---------------------------------------------------------------------------


def _session_factory():
    """Return a Session context manager for the job store (injected, not imported)."""
    from common_lib.modules.data_storage.database.connection import _get_db_service

    return _get_db_service().get_session()


def configure_job_store() -> bool:
    """Attach the DB-backed store to the JobService singleton (idempotent).

    Called at import time, which happens while routers are registered — before
    the lifespan runs ``init_db()`` — so this only wires the factory: no DB
    traffic occurs until the first job record is persisted.
    """
    if _state["configured"]:
        return True
    try:
        get_job_service().set_store(JobStore(session_factory=_session_factory))
        _state["configured"] = True
        return True
    except Exception as exc:  # noqa: BLE001 - jobs still work from memory
        logger.warning("jobs: could not configure DB store: %s", exc)
        return False


def _ensure_rehydrated() -> None:
    """Load persisted records once, after startup (best-effort)."""
    if _state["rehydrated"]:
        return
    _state["rehydrated"] = True
    if not _state["configured"]:
        return
    try:
        restored: int = get_job_service().rehydrate()
        if restored:
            logger.info("jobs: rehydrated %d record(s) from the database", restored)
    except Exception as exc:  # noqa: BLE001
        logger.warning("jobs: rehydrate failed: %s", exc)


configure_job_store()


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------


class JobCancelResponse(BaseModel):
    job_id: str = Field(description="Cancelled job id")
    status: str = Field(description="Resulting job status")


class JobCleanupResponse(BaseModel):
    removed: int = Field(description="Number of terminal records removed")


def _dump(record: JobRecord) -> dict[str, Any]:
    return record.to_dict()


def _get_or_404(job_id: str) -> JobRecord:
    record: Optional[JobRecord] = get_job_service().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return record


# ---------------------------------------------------------------------------
# Read / list / cancel
# ---------------------------------------------------------------------------


@router.get("/")
def list_jobs(
    identity: Annotated[PlatformIdentity, Depends(get_current_identity)],
    user_id: Optional[str] = Query(None, description="Filter by owner (admin-style)"),
    status: Optional[str] = Query(None, description="queued|running|completed|failed|cancelled"),
    kind: Optional[str] = Query(None, description="Exact job kind, e.g. audio.tts"),
    kind_prefix: Optional[str] = Query(
        None, description="Kind prefix filter, e.g. audio."
    ),
    mine: bool = Query(False, description="Only jobs submitted by the caller"),
    limit: int = Query(100, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List background jobs newest-first with optional filters."""
    _ensure_rehydrated()
    owner: Optional[str] = str(identity.subject_id) if mine else user_id
    records: list[JobRecord] = get_job_service().list(
        user_id=owner,
        status=status,
        kind=kind,
        kind_prefix=kind_prefix,
        limit=limit,
        offset=offset,
    )
    payload: list[dict[str, Any]] = [_dump(record) for record in records]
    return {"data": payload, "total": len(payload)}


@router.get("/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    """Return one job record (status, progress, result_refs, error)."""
    _ensure_rehydrated()
    return {"data": _dump(_get_or_404(job_id))}


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    """Request cooperative cancellation of a queued/running job."""
    record: Optional[JobRecord] = get_job_service().cancel(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    response = JobCancelResponse(job_id=record.id, status=record.status)
    return {"data": response.model_dump()}


# ---------------------------------------------------------------------------
# Progress push (SSE)
# ---------------------------------------------------------------------------


async def _job_event_stream(job_id: str, request: Request) -> AsyncGenerator[str, None]:
    """Yield SSE events for one job until it reaches a terminal status."""
    service = get_job_service()
    last: str = ""
    waited: float = 0.0
    yield (
        "event: started\n"
        f"data: {json.dumps({'job_id': job_id, 'status': JobStatus.QUEUED})}\n\n"
    )
    while waited < SSE_TIMEOUT_SECONDS:
        if await request.is_disconnected():
            return
        record: Optional[JobRecord] = service.get(job_id)
        if record is None:
            yield (
                "event: failed\n"
                f"data: {json.dumps({'job_id': job_id, 'error': 'job not found'})}\n\n"
            )
            return
        fingerprint: str = f"{record.status}:{record.progress}"
        if fingerprint != last:
            last = fingerprint
            yield (
                "event: progress\n"
                f"data: {json.dumps({'job_id': job_id, 'status': record.status, 'progress': record.progress})}\n\n"
            )
        if record.status in TERMINAL_STATUSES:
            event_data: dict[str, Any] = {
                "job_id": job_id,
                "status": record.status,
                "progress": record.progress,
                "result_refs": record.get_result_refs(),
                "error": record.error,
            }
            yield f"event: {record.status}\ndata: {json.dumps(event_data)}\n\n"
            return
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        waited += POLL_INTERVAL_SECONDS
    yield (
        "event: timeout\n"
        f"data: {json.dumps({'job_id': job_id, 'error': 'progress stream timed out'})}\n\n"
    )


@router.get("/{job_id}/events")
async def job_events(job_id: str, request: Request) -> StreamingResponse:
    """Stream job status/progress as SSE (started, progress, completed/failed/cancelled)."""
    _ensure_rehydrated()
    _get_or_404(job_id)
    return StreamingResponse(
        _job_event_stream(job_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


@router.post("/cleanup")
def cleanup_jobs(
    max_age_seconds: float = Query(86400.0, ge=0.0),
    limit: int = Query(500, ge=1, le=5000),
    remove_artifacts: bool = Query(False),
    statuses: Optional[str] = Query(
        None, description="Comma-separated terminal statuses to prune"
    ),
) -> dict[str, Any]:
    """Drop terminal job records older than ``max_age_seconds``."""
    selected: tuple[str, ...] = TERMINAL_STATUSES
    if statuses:
        requested: list[str] = [s.strip() for s in statuses.split(",") if s.strip()]
        invalid: list[str] = [s for s in requested if s not in TERMINAL_STATUSES]
        if invalid:
            raise HTTPException(
                status_code=400, detail=f"Not terminal statuses: {invalid}"
            )
        selected = tuple(requested)
    removed: int = get_job_service().cleanup(
        max_age_seconds=max_age_seconds,
        statuses=selected,
        limit=limit,
        remove_artifacts=remove_artifacts,
    )
    response = JobCleanupResponse(removed=removed)
    return {"data": response.model_dump()}
