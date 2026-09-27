# DAW Routes - REST API for DAW projects
from fastapi import APIRouter, HTTPException, Depends, Depends
from uuid import UUID
from typing import List, Annotated, Optional, Dict, Any
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.audio_processing.daw.schemas import (
    DAWProjectCreate,
    DAWProjectUpdate,
    DAWProjectResponse,
    ChannelCreate,
    ChannelUpdate,
    ChannelResponse,
    PatternCreate,
    PatternUpdate,
    PatternResponse,
    NoteCreate,
    NoteUpdate,
    NoteResponse,
    ClipCreate,
    ClipUpdate,
    ClipResponse,
    DAWExport,
)
from common_lib.modules.audio_processing.daw.service import daw_service, NotFoundError

from app.modules.daw.runtime.actor import capture_job_actor, owned_job_service
from common_lib.modules.jobs.artifacts import job_dir
from common_lib.modules.jobs.models import JobRecord
from common_lib.modules.jobs.service import get_job_service

MOCK_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

router = APIRouter(prefix="/daw", tags=["DAW"], dependencies=[Depends(capture_job_actor)])


# ---------------------------------------------------------------------------
# Jobs-backed execution helpers
# ---------------------------------------------------------------------------


def _ensure_daw_jobs():
    """Register DAW executors and return the actor-aware JobService proxy."""
    return owned_job_service()


def _daw_job_payload(record: Any) -> Dict[str, Any]:
    refs: List[str] = []
    try:
        refs = [str(r) for r in (record.get_result_refs() or [])]
    except Exception:
        refs = []
    return {
        "job_id": str(record.id),
        "status": str(record.status),
        "kind": str(record.kind),
        "progress": float(record.progress or 0.0),
        "result_refs": refs,
        "error": record.error,
    }


def _daw_job_status(job_id: str) -> Dict[str, Any]:
    """Jobs-backed status view."""
    from fastapi import HTTPException as _HTTPException

    svc = _ensure_daw_jobs()
    record = svc.get(job_id)
    if record is None:
        raise _HTTPException(status_code=404, detail=f"Job {job_id} not found")
    payload: Dict[str, Any] = _daw_job_payload(record)
    meta: Dict[str, Any] = {}
    try:
        refs = [str(r) for r in (record.get_result_refs() or [])]
    except Exception:
        refs = []
    for ref in refs:
        if not ref.endswith("result.json"):
            continue
        try:
            import json
            with open(ref, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                meta = loaded
                break
        except (OSError, ValueError):
            continue
    payload["meta"] = meta
    return payload


# ---------------------------------------------------------------------------
# Jobs endpoints
# ---------------------------------------------------------------------------


@router.get("/jobs")
async def list_daw_jobs(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List background DAW jobs (newest first), newest-first with filters."""
    records = _ensure_daw_jobs().list(
        status=status,
        kind=kind,
        kind_prefix="daw.",
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
    )
    items = [_daw_job_payload(record) for record in records]
    return {"data": items, "total": len(items)}


@router.get("/jobs/{job_id}")
async def get_daw_job(job_id: str) -> Dict[str, Any]:
    """Poll a jobs-backed DAW job (progress, result_refs, result.json meta)."""
    return _daw_job_status(job_id)


@router.post("/jobs/{job_id}/cancel")
async def cancel_daw_job(job_id: str) -> Dict[str, Any]:
    """Cooperatively cancel a queued/running DAW job."""
    record = _ensure_daw_jobs().cancel(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"status": "ok", **_daw_job_payload(record)}


@router.get("/jobs/{job_id}/events")
async def daw_job_events(job_id: str):
    """Stream SSE progress events backed by DAW job progress."""
    from fastapi.responses import StreamingResponse
    import asyncio
    import json
    import time as _time

    async def event_generator():
        deadline: float = _time.time() + 3600.0  # 1 hour max
        last_progress: float = -1.0
        yield f"event: started\ndata: {json.dumps({'job_id': job_id, 'status': 'queued'})}\n\n"
        while True:
            record: JobRecord | None = get_job_service().get(job_id)
            if record is None:
                yield f"event: failed\ndata: {json.dumps({'job_id': job_id, 'error': 'job not found'})}\n\n"
                return
            if record.progress != last_progress:
                last_progress = record.progress
                yield f"event: progress\ndata: {json.dumps({'job_id': job_id, 'status': record.status, 'progress': record.progress})}\n\n"
            if record.status in ("completed", "failed", "cancelled"):
                if record.status == "completed":
                    meta: Dict[str, Any] = {}
                    for ref in _daw_job_payload(record)["result_refs"]:
                        if not ref.endswith("result.json"):
                            continue
                        try:
                            with open(ref, "r", encoding="utf-8") as fh:
                                loaded = json.load(fh)
                            if isinstance(loaded, dict):
                                meta = loaded
                                break
                        except (OSError, ValueError):
                            continue
                    yield f"event: completed\ndata: {json.dumps({'job_id': job_id, 'status': 'completed', 'meta': meta})}\n\n"
                else:
                    yield f"event: {record.status}\ndata: {json.dumps({'job_id': job_id, 'status': record.status, 'error': record.error or record.status})}\n\n"
                return
            if _time.time() > deadline:
                yield f"event: timeout\ndata: {json.dumps({'job_id': job_id, 'error': 'progress stream timed out'})}\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/projects", response_model=DAWProjectResponse)
async def create_project(
    data: DAWProjectCreate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.create_project(session, MOCK_USER_ID, data)


@router.get("/projects", response_model=List[DAWProjectResponse])
async def list_projects(
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.get_user_projects(session, MOCK_USER_ID)


@router.get("/projects/{project_id}", response_model=DAWProjectResponse)
async def get_project(
    project_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    project = daw_service.get_project_with_details(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/projects/{project_id}", response_model=DAWProjectResponse)
async def update_project(
    project_id: UUID,
    data: DAWProjectUpdate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.update_project(session, project_id, data)


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    daw_service.delete(session, project_id)
    return {"status": "deleted"}


@router.post("/projects/{project_id}/channels", response_model=ChannelResponse)
async def create_channel(
    project_id: UUID,
    data: ChannelCreate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.create_channel(session, project_id, data)


@router.patch("/channels/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: UUID,
    data: ChannelUpdate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.update_channel(session, channel_id, data)


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    daw_service.delete_channel(session, channel_id)
    return {"status": "deleted"}


@router.post("/projects/{project_id}/patterns", response_model=PatternResponse)
async def create_pattern(
    project_id: UUID,
    data: PatternCreate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.create_pattern(session, project_id, data)


@router.patch("/patterns/{pattern_id}", response_model=PatternResponse)
async def update_pattern(
    pattern_id: UUID,
    data: PatternUpdate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.update_pattern(session, pattern_id, data)


@router.post("/patterns/{pattern_id}/notes", response_model=NoteResponse)
async def add_note(
    pattern_id: UUID,
    data: NoteCreate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.add_note(session, pattern_id, data)


@router.patch("/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: UUID,
    data: NoteUpdate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.update_note(session, note_id, data)


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    daw_service.delete_note(session, note_id)
    return {"status": "deleted"}


@router.post("/projects/{project_id}/clips", response_model=ClipResponse)
async def create_clip(
    project_id: UUID,
    data: ClipCreate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.create_clip(session, project_id, data)


@router.patch("/clips/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: UUID,
    data: ClipUpdate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.update_clip(session, clip_id, data)


@router.delete("/clips/{clip_id}")
async def delete_clip(
    clip_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    daw_service.delete_clip(session, clip_id)
    return {"status": "deleted"}


@router.get("/projects/{project_id}/export", response_model=DAWExport)
async def export_project(
    project_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    sync: bool = False,
):
    """Export a DAW project.

    Jobs-backed by default; pass ``sync=true`` to run inline.
    """
    if sync:
        return daw_service.export_project(session, project_id)

    from app.modules.daw.runtime.job_executors import EXPORT_PROJECT_KIND

    record = _ensure_daw_jobs().submit(
        EXPORT_PROJECT_KIND, params={"project_id": str(project_id)}
    )
    return {"status": "queued", **_daw_job_payload(record)}


__all__ = ["router"]
