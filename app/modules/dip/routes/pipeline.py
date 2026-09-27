from fastapi import APIRouter, Body, HTTPException, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from common_lib.modules.dip.pipeline.controller import (
    run_pipeline,
    get_pipeline_executions,
    get_pipeline_status,
    validate_workflow,
)

from app.modules.dip.runtime.actor import capture_job_actor, owned_job_service
from common_lib.modules.jobs.artifacts import job_dir
from common_lib.modules.jobs.models import JobRecord
from common_lib.modules.jobs.service import get_job_service

router = APIRouter(prefix="/dip/pipeline", tags=["dip/pipeline"], dependencies=[Depends(capture_job_actor)])
pipeline_router = router


# ---------------------------------------------------------------------------
# Jobs-backed execution helpers
# ---------------------------------------------------------------------------


def _ensure_dip_jobs():
    return owned_job_service()


def _dip_job_payload(record: Any) -> Dict[str, Any]:
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


def _dip_job_status(job_id: str) -> Dict[str, Any]:
    from fastapi import HTTPException as _HTTPException
    import json

    svc = _ensure_dip_jobs()
    record = svc.get(job_id)
    if record is None:
        raise _HTTPException(status_code=404, detail=f"Job {job_id} not found")
    payload: Dict[str, Any] = _dip_job_payload(record)
    meta: Dict[str, Any] = {}
    try:
        refs = [str(r) for r in (record.get_result_refs() or [])]
    except Exception:
        refs = []
    for ref in refs:
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
    payload["meta"] = meta
    return payload


# ---------------------------------------------------------------------------
# Jobs endpoints
# ---------------------------------------------------------------------------


@router.get("/jobs")
async def list_dip_pipeline_jobs(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    records = _ensure_dip_jobs().list(
        status=status,
        kind=kind,
        kind_prefix="dip.",
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
    )
    items = [_dip_job_payload(record) for record in records]
    return {"data": items, "total": len(items)}


@router.get("/jobs/{job_id}")
async def get_dip_pipeline_job(job_id: str) -> Dict[str, Any]:
    return _dip_job_status(job_id)


@router.post("/jobs/{job_id}/cancel")
async def cancel_dip_pipeline_job(job_id: str) -> Dict[str, Any]:
    record = _ensure_dip_jobs().cancel(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"status": "ok", **_dip_job_payload(record)}


@router.get("/jobs/{job_id}/events")
async def dip_pipeline_job_events(job_id: str):
    from fastapi.responses import StreamingResponse
    import json
    import asyncio
    import time as _time

    async def event_generator():
        deadline: float = _time.time() + 3600.0
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
                    for ref in _dip_job_payload(record)["result_refs"]:
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


class PipelineRunRequest(BaseModel):
    name: str
    workflow_yaml: str
    source_folder: str
    output_dest: str = "raw"


class ValidateRequest(BaseModel):
    workflow_yaml: str


@router.post("/run")
async def create_pipeline_run(req: PipelineRunRequest, sync: bool = False):
    """Run a pipeline. Jobs-backed by default; pass ``sync=true`` for inline."""
    if sync:
        return await run_pipeline(
            req.name, req.workflow_yaml, req.source_folder, req.output_dest
        )

    from app.modules.dip.runtime.job_executors import PIPELINE_RUN_KIND

    record = _ensure_dip_jobs().submit(
        PIPELINE_RUN_KIND,
        params={
            "name": req.name,
            "workflow_yaml": req.workflow_yaml,
            "source_folder": req.source_folder,
            "output_dest": req.output_dest,
        },
    )
    return {"status": "queued", **_dip_job_payload(record)}


@router.get("/executions")
async def list_executions():
    return await get_pipeline_executions()


@router.get("/status/{execution_id}")
async def get_execution_status(execution_id: str):
    return await get_pipeline_status(execution_id)


@router.post("/validate")
async def validate(req: ValidateRequest):
    return await validate_workflow(req.workflow_yaml)
