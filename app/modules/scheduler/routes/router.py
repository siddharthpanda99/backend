"""Scheduler API Routes - CRUD for cron jobs and scheduled workflows.

Provides REST endpoints for managing scheduled cron jobs:
- Create, read, update, delete cron jobs
- Enable/disable/pause/resume jobs
- Trigger jobs manually
- Get scheduler statistics
- SSE stream for real-time job status updates
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/scheduler", tags=["scheduler"])

logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


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


# =============================================================================
# CRUD Endpoints
# =============================================================================


@router.post("/jobs")
async def create_cron_job(request: CreateCronJobRequest):
    """Create a new scheduled cron job."""
    try:
        from app.modules.scheduler.service import get_scheduler_service

        service = get_scheduler_service()

        job_data = request.model_dump()
        job = service.create_job(job_data)

        return {
            "status": "ok",
            "message": f"Cron job '{job.name}' created",
            "job": job.to_dict(),
        }
    except Exception as e:
        logger.error(f"Failed to create cron job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs")
async def list_cron_jobs(
    status: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
):
    """List all cron jobs with optional filters."""
    try:
        from app.modules.scheduler.service import get_scheduler_service

        service = get_scheduler_service()
        jobs = service.list_jobs(status=status, enabled=enabled)

        return {
            "status": "ok",
            "jobs": [j.to_dict() for j in jobs],
            "count": len(jobs),
        }
    except Exception as e:
        logger.error(f"Failed to list cron jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}")
async def get_cron_job(job_id: str):
    """Get a specific cron job by ID."""
    try:
        from app.modules.scheduler.service import get_scheduler_service

        service = get_scheduler_service()
        job = service.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        return {
            "status": "ok",
            "job": job.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cron job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/jobs/{job_id}")
async def update_cron_job(job_id: str, request: UpdateCronJobRequest):
    """Update a cron job."""
    try:
        from app.modules.scheduler.service import get_scheduler_service

        service = get_scheduler_service()
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        job = service.update_job(job_id, updates)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        return {
            "status": "ok",
            "message": f"Cron job '{job.name}' updated",
            "job": job.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update cron job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/jobs/{job_id}")
async def delete_cron_job(job_id: str):
    """Delete a cron job."""
    try:
        from app.modules.scheduler.service import get_scheduler_service

        service = get_scheduler_service()
        success = service.delete_job(job_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        return {
            "status": "ok",
            "message": f"Cron job '{job_id}' deleted",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete cron job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Control Endpoints
# =============================================================================


@router.post("/jobs/{job_id}/enable")
async def enable_cron_job(job_id: str):
    """Enable a cron job."""
    try:
        from app.modules.scheduler.service import get_scheduler_service

        service = get_scheduler_service()
        job = service.enable_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        return {
            "status": "ok",
            "message": f"Cron job '{job.name}' enabled",
            "job": job.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable cron job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/disable")
async def disable_cron_job(job_id: str):
    """Disable a cron job."""
    try:
        from app.modules.scheduler.service import get_scheduler_service

        service = get_scheduler_service()
        job = service.disable_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        return {
            "status": "ok",
            "message": f"Cron job '{job.name}' disabled",
            "job": job.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable cron job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/pause")
async def pause_cron_job(job_id: str):
    """Pause a cron job."""
    try:
        from app.modules.scheduler.service import get_scheduler_service

        service = get_scheduler_service()
        job = service.pause_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        return {
            "status": "ok",
            "message": f"Cron job '{job.name}' paused",
            "job": job.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause cron job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/resume")
async def resume_cron_job(job_id: str):
    """Resume a paused cron job."""
    try:
        from app.modules.scheduler.service import get_scheduler_service

        service = get_scheduler_service()
        job = service.resume_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        return {
            "status": "ok",
            "message": f"Cron job '{job.name}' resumed",
            "job": job.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume cron job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/run")
async def run_cron_job_now(job_id: str):
    """Trigger a cron job to run immediately."""
    try:
        from app.modules.scheduler.service import get_scheduler_service

        service = get_scheduler_service()
        result = await service.run_job_now(job_id)

        if result is None:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        return {
            "status": "ok",
            "message": f"Cron job '{job_id}' triggered",
            "result": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run cron job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Statistics
# =============================================================================


@router.get("/stats")
async def scheduler_stats():
    """Get scheduler statistics."""
    try:
        from app.modules.scheduler.service import get_scheduler_service

        service = get_scheduler_service()
        return {
            "status": "ok",
            "stats": service.get_stats(),
        }
    except Exception as e:
        logger.error(f"Failed to get scheduler stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Workflow Catalog
# =============================================================================


@router.get("/workflows")
async def list_available_workflows():
    """List all registered workflow executors available for scheduling."""
    try:
        from app.modules.scheduler.workflow_registry import list_workflows

        workflows = list_workflows()
        templates = {
            "sd_news_reddit": {
                "name": "Reddit SD News",
                "description": "Fetches Stable Diffusion news from Reddit subreddits",
                "default_inputs": {
                    "subreddits": [
                        {"name": "StableDiffusion", "sort": "hot", "limit": 15},
                        {"name": "sdforall", "sort": "hot", "limit": 10},
                        {"name": "aiArt", "sort": "hot", "limit": 10},
                    ],
                    "limit": 25,
                    "sort": "hot",
                    "send_notification": True,
                },
                "default_interval_minutes": 5.0,
            },
            "rag_pipeline": {
                "name": "RAG Document Pipeline",
                "description": "Document ingestion, chunking, embedding, and retrieval",
                "default_inputs": {
                    "source_type": "local",
                    "source_path": "/data/documents",
                    "chunk_size": 1000,
                    "top_k": 5,
                },
                "default_interval_minutes": 60.0,
            },
            "pii_compliance": {
                "name": "PII Compliance Scan",
                "description": "Scan data for PII, anonymize, generate audit report",
                "default_inputs": {
                    "data_source": "/data/storage",
                    "entities": "PERSON,EMAIL,PHONE_NUMBER",
                    "anonymize": True,
                },
                "default_interval_minutes": 1440.0,
            },
            "memory_security_audit": {
                "name": "Memory Security Audit",
                "description": "PII scan, GDPR compliance, right-to-forget execution",
                "default_inputs": {
                    "agent_id": "default",
                    "max_retention_days": 365,
                    "hard_delete": False,
                },
                "default_interval_minutes": 1440.0,
            },
            "memory_observability": {
                "name": "Memory Observability",
                "description": "Collect metrics, trace performance, health checks",
                "default_inputs": {
                    "window": "24h",
                },
                "default_interval_minutes": 30.0,
            },
            "memory_economics_tracking": {
                "name": "Memory Economics",
                "description": "Track embedding/storage costs, budget management",
                "default_inputs": {
                    "agent_id": "default",
                    "period": "monthly",
                },
                "default_interval_minutes": 1440.0,
            },
            "memory_federation_sync": {
                "name": "Memory Federation Sync",
                "description": "Sync memories across federated nodes",
                "default_inputs": {
                    "seed_nodes": [],
                    "max_hops": 3,
                    "conflict_strategy": "latest",
                },
                "default_interval_minutes": 15.0,
            },
        }
        return {
            "status": "ok",
            "workflows": workflows,
            "templates": templates,
        }
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class CreateFromTemplateRequest(BaseModel):
    template_id: str
    overrides: Dict[str, Any] = {}


@router.post("/jobs/from-template")
async def create_job_from_template(request: CreateFromTemplateRequest):
    """Create a cron job from a workflow template."""
    try:
        from app.modules.scheduler.service import get_scheduler_service

        template_id = request.template_id
        overrides = request.overrides

        templates = {
            "sd_news_reddit": {
                "name": "Reddit SD News",
                "description": "Fetches Stable Diffusion news from Reddit subreddits",
                "workflow_id": "sd_news_reddit",
                "workflow_name": "Reddit SD News Scraper",
                "interval_minutes": 5.0,
                "workflow_inputs": {
                    "subreddits": [
                        {"name": "StableDiffusion", "sort": "hot", "limit": 15},
                        {"name": "sdforall", "sort": "hot", "limit": 10},
                        {"name": "aiArt", "sort": "hot", "limit": 10},
                    ],
                    "limit": 25,
                    "sort": "hot",
                    "send_notification": True,
                },
            },
            "rag_pipeline": {
                "name": "RAG Document Pipeline",
                "description": "Document ingestion, chunking, embedding, and retrieval",
                "workflow_id": "rag_pipeline",
                "workflow_name": "RAG Pipeline",
                "interval_minutes": 60.0,
                "workflow_inputs": {
                    "source_type": "local",
                    "source_path": "/data/documents",
                    "chunk_size": 1000,
                    "top_k": 5,
                },
            },
            "pii_compliance": {
                "name": "PII Compliance Scan",
                "description": "Scan data for PII, anonymize, generate audit report",
                "workflow_id": "pii_compliance",
                "workflow_name": "PII Compliance",
                "interval_minutes": 1440.0,
                "workflow_inputs": {
                    "data_source": "/data/storage",
                    "entities": "PERSON,EMAIL,PHONE_NUMBER",
                    "anonymize": True,
                },
            },
            "memory_security_audit": {
                "name": "Memory Security Audit",
                "description": "PII scan, GDPR compliance, right-to-forget",
                "workflow_id": "memory_security_audit",
                "workflow_name": "Memory Security Audit",
                "interval_minutes": 1440.0,
                "workflow_inputs": {
                    "agent_id": "default",
                    "max_retention_days": 365,
                    "hard_delete": False,
                },
            },
            "memory_observability": {
                "name": "Memory Observability",
                "description": "Collect metrics, trace performance, health checks",
                "workflow_id": "memory_observability",
                "workflow_name": "Memory Observability",
                "interval_minutes": 30.0,
                "workflow_inputs": {"window": "24h"},
            },
            "memory_economics_tracking": {
                "name": "Memory Economics",
                "description": "Track embedding/storage costs, budget management",
                "workflow_id": "memory_economics_tracking",
                "workflow_name": "Memory Economics",
                "interval_minutes": 1440.0,
                "workflow_inputs": {"agent_id": "default", "period": "monthly"},
            },
            "memory_federation_sync": {
                "name": "Memory Federation Sync",
                "description": "Sync memories across federated nodes",
                "workflow_id": "memory_federation_sync",
                "workflow_name": "Memory Federation Sync",
                "interval_minutes": 15.0,
                "workflow_inputs": {
                    "seed_nodes": [],
                    "max_hops": 3,
                    "conflict_strategy": "latest",
                },
            },
        }

        if template_id not in templates:
            raise HTTPException(
                status_code=404,
                detail=f"Template not found: {template_id}. Available: {list(templates.keys())}",
            )

        template = templates[template_id]
        job_data = {**template, **overrides}

        service = get_scheduler_service()
        job = service.create_job(job_data)

        return {
            "status": "ok",
            "message": f"Cron job '{job.name}' created from template",
            "job": job.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create job from template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SSE Real-time Stream
# =============================================================================


async def _sse_generator(job_id: Optional[str] = None):
    """SSE generator that streams cron job events."""
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
    """SSE endpoint for real-time cron job status updates.

    Subscribe to all job events or filter by job_id.
    Events include: cron.success, cron.failed, cron_job_result.
    """
    return StreamingResponse(
        _sse_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
