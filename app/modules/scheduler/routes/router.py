"""Scheduler API Routes — thin router delegating to SchedulerService."""

import asyncio
import json
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from common_lib.modules.scheduler.service import get_scheduler_service

router = APIRouter(prefix="/scheduler", tags=["scheduler"])
logger = logging.getLogger(__name__)


class CreateCronJobRequest(BaseModel):
    name: str
    description: str = ""
    enabled: bool = True
    trigger_type: str = "interval"
    interval_minutes: float = 5.0
    cron_expression: str = "*/5 * * * *"
    workflow_id: str = ""
    workflow_name: str = ""
    workflow_inputs: Dict[str, Any] = {}
    notification_channel: str = "global"
    notification_enabled: bool = True
    notification_on_success: bool = True
    notification_on_failure: bool = True
    max_retries: int = 3
    timeout_seconds: float = 300.0
    metadata: Dict[str, Any] = {}


class UpdateCronJobRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    trigger_type: Optional[str] = None
    interval_minutes: Optional[float] = None
    cron_expression: Optional[str] = None
    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None
    workflow_inputs: Optional[Dict[str, Any]] = None
    notification_channel: Optional[str] = None
    notification_enabled: Optional[bool] = None
    notification_on_success: Optional[bool] = None
    notification_on_failure: Optional[bool] = None
    max_retries: Optional[int] = None
    timeout_seconds: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class CreateFromTemplateRequest(BaseModel):
    template_id: str
    overrides: Dict[str, Any] = {}


def _get_service():
    return get_scheduler_service()


@router.post("/jobs")
async def create_cron_job(request: CreateCronJobRequest):
    service = _get_service()
    job = service.create_job(request.model_dump())
    return {
        "status": "ok",
        "message": f"Cron job '{job.name}' created",
        "job": job.to_dict(),
    }


@router.get("/jobs")
async def list_cron_jobs(
    status: Optional[str] = Query(None), enabled: Optional[bool] = Query(None)
):
    service = _get_service()
    jobs = service.list_jobs(status=status, enabled=enabled)
    return {"status": "ok", "jobs": [j.to_dict() for j in jobs], "count": len(jobs)}


@router.get("/jobs/{job_id}")
async def get_cron_job(job_id: str):
    service = _get_service()
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {"status": "ok", "job": job.to_dict()}


@router.put("/jobs/{job_id}")
async def update_cron_job(job_id: str, request: UpdateCronJobRequest):
    service = _get_service()
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    job = service.update_job(job_id, updates)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {
        "status": "ok",
        "message": f"Cron job '{job.name}' updated",
        "job": job.to_dict(),
    }


@router.delete("/jobs/{job_id}")
async def delete_cron_job(job_id: str):
    service = _get_service()
    if not service.delete_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {"status": "ok", "message": f"Cron job '{job_id}' deleted"}


@router.post("/jobs/{job_id}/enable")
async def enable_cron_job(job_id: str):
    service = _get_service()
    job = service.enable_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {
        "status": "ok",
        "message": f"Cron job '{job.name}' enabled",
        "job": job.to_dict(),
    }


@router.post("/jobs/{job_id}/disable")
async def disable_cron_job(job_id: str):
    service = _get_service()
    job = service.disable_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {
        "status": "ok",
        "message": f"Cron job '{job.name}' disabled",
        "job": job.to_dict(),
    }


@router.post("/jobs/{job_id}/pause")
async def pause_cron_job(job_id: str):
    service = _get_service()
    job = service.pause_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {
        "status": "ok",
        "message": f"Cron job '{job.name}' paused",
        "job": job.to_dict(),
    }


@router.post("/jobs/{job_id}/resume")
async def resume_cron_job(job_id: str):
    service = _get_service()
    job = service.resume_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {
        "status": "ok",
        "message": f"Cron job '{job.name}' resumed",
        "job": job.to_dict(),
    }


@router.post("/jobs/{job_id}/run")
async def run_cron_job_now(job_id: str):
    service = _get_service()
    result = await service.run_job_now(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {
        "status": "ok",
        "message": f"Cron job '{job_id}' triggered",
        "result": result,
    }


@router.get("/stats")
async def scheduler_stats():
    service = _get_service()
    return {"status": "ok", "stats": service.get_stats()}


@router.get("/workflows")
async def list_available_workflows():
    from common_lib.modules.scheduler.workflow_registry import list_workflows

    service = _get_service()
    workflows = list_workflows()
    templates = service.list_templates()
    return {"status": "ok", "workflows": workflows, "templates": templates}


@router.post("/jobs/from-template")
async def create_job_from_template(request: CreateFromTemplateRequest):
    service = _get_service()
    job = service.create_job_from_template(request.template_id, request.overrides)
    if not job:
        available = list(service.list_templates().keys())
        raise HTTPException(
            status_code=404,
            detail=f"Template not found: {request.template_id}. Available: {available}",
        )
    return {
        "status": "ok",
        "message": f"Cron job '{job.name}' created from template",
        "job": job.to_dict(),
    }


async def _sse_generator(job_id: Optional[str] = None):
    from common_lib.modules.notification.controller import (
        get_notification_service,
        Channels,
    )

    service = get_notification_service()
    queue = service.subscribe(Channels.GLOBAL)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                data = event.get("data", {})
                event_type = event.get("event_type", "")
                if "cron" in event_type or data.get("type") == "cron_job_result":
                    if job_id and data.get("job_id") != job_id:
                        continue
                    yield f"data: {json.dumps(event, default=str)}\n\n"
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        service.unsubscribe(Channels.GLOBAL, queue)


@router.get("/stream")
async def stream_jobs(job_id: Optional[str] = Query(None)):
    return StreamingResponse(
        _sse_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
