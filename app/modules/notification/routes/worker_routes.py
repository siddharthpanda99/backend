"""Notification Workers — API routes.

REST endpoints for managing worker tasks, running workers, and broadcast jobs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workers", tags=["Notification — Workers"])


# ── Request Schemas ─────────────────────────────────────────────────


class EnqueueDeliveryRequest(BaseModel):
    event_id: str
    subscriber_id: str
    channel: str = "in_app"
    template_id: str = ""
    priority: int = 0


class EnqueueRetryRequest(BaseModel):
    event_id: str
    subscriber_id: str
    channel: str
    error: str = ""
    max_attempts: int = 3


class StartBroadcastRequest(BaseModel):
    campaign_id: str
    template_id: str
    recipient_ids: List[str]
    channel: str = "email"
    notification_type: str = "broadcast"
    batch_size: int = 50


class CreateCleanupPolicyRequest(BaseModel):
    name: str
    target: str
    retention_days: int = 90
    schedule_cron: str = "0 3 * * *"


# ── Dependencies ────────────────────────────────────────────────────


def _get_session():
    from app.modules.project_management.deps import get_pm_session
    import inspect
    # Use the synchronous session
    return get_pm_session()


def _get_task_svc(session=None):
    from common_lib.modules.notification.workers.service import WorkerTaskService
    if session is None:
        session = _get_session()
    return WorkerTaskService(session=session)


# ── Delivery Worker Routes ──────────────────────────────────────────


@router.post("/delivery/enqueue")
async def enqueue_delivery(request: EnqueueDeliveryRequest) -> Dict[str, Any]:
    """Enqueue a delivery task."""
    session = _get_session()
    try:
        svc = _get_task_svc(session)
        return svc.enqueue(
            worker_type="delivery", queue_name="immediate",
            task_type="delivery_dispatch",
            payload=request.model_dump(),
            priority=request.priority,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/delivery/run-batch")
async def run_delivery_batch(limit: int = Query(5, ge=1, le=100)) -> Dict[str, Any]:
    """Run one batch of the DeliveryWorker."""
    import asyncio
    session = _get_session()
    try:
        from common_lib.modules.notification.workers.service import DeliveryWorker
        worker = DeliveryWorker(session=session)
        return asyncio.run(worker.run_once(limit=limit))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ── Retry Worker Routes ─────────────────────────────────────────────


@router.post("/retry/enqueue")
async def enqueue_retry(request: EnqueueRetryRequest) -> Dict[str, Any]:
    """Enqueue a retry task."""
    session = _get_session()
    try:
        svc = _get_task_svc(session)
        return svc.enqueue(
            worker_type="retry", queue_name="retry",
            task_type="delivery_retry",
            payload=request.model_dump(),
            max_attempts=request.max_attempts,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/retry/run-batch")
async def run_retry_batch(limit: int = Query(5, ge=1, le=50)) -> Dict[str, Any]:
    """Run one batch of the RetryWorker."""
    import asyncio
    session = _get_session()
    try:
        from common_lib.modules.notification.workers.service import RetryWorker
        worker = RetryWorker(session=session)
        return asyncio.run(worker.run_once(limit=limit))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ── Broadcast Worker Routes ─────────────────────────────────────────


@router.post("/broadcast/start")
async def start_broadcast(request: StartBroadcastRequest) -> Dict[str, Any]:
    """Start a broadcast campaign."""
    session = _get_session()
    try:
        from common_lib.modules.notification.workers.service import BroadcastWorker
        worker = BroadcastWorker(session=session)
        return worker.start_broadcast(
            campaign_id=request.campaign_id, template_id=request.template_id,
            recipient_ids=request.recipient_ids, channel=request.channel,
            notification_type=request.notification_type, batch_size=request.batch_size,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/broadcast/{campaign_id}/progress")
async def get_broadcast_progress(campaign_id: str) -> Dict[str, Any]:
    """Get broadcast campaign progress."""
    session = _get_session()
    try:
        from common_lib.modules.notification.workers.service import BroadcastWorker
        worker = BroadcastWorker(session=session)
        result = worker.get_broadcast_progress(campaign_id=campaign_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Broadcast job not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/broadcast/{campaign_id}/pause")
async def pause_broadcast(campaign_id: str) -> Dict[str, Any]:
    """Pause a running broadcast."""
    session = _get_session()
    try:
        from common_lib.modules.notification.workers.service import BroadcastWorker
        worker = BroadcastWorker(session=session)
        paused = worker.pause_broadcast(campaign_id=campaign_id)
        return {"paused": paused, "campaign_id": campaign_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/broadcast/{campaign_id}/resume")
async def resume_broadcast(campaign_id: str) -> Dict[str, Any]:
    """Resume a paused broadcast."""
    session = _get_session()
    try:
        from common_lib.modules.notification.workers.service import BroadcastWorker
        worker = BroadcastWorker(session=session)
        resumed = worker.resume_broadcast(campaign_id=campaign_id)
        return {"resumed": resumed, "campaign_id": campaign_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ── Cleanup Worker Routes ───────────────────────────────────────────


@router.post("/cleanup/run")
async def run_cleanup(retention_days: int = Query(90, ge=30, le=730),
                       batch_size: int = Query(500, ge=50, le=5000)) -> Dict[str, Any]:
    """Run the CleanupWorker — archive old data, prune stale tokens."""
    import asyncio
    session = _get_session()
    try:
        from common_lib.modules.notification.workers.service import CleanupWorker
        worker = CleanupWorker(session=session)
        result = asyncio.run(worker._run_cleanup_policy({
            "retention_days": retention_days, "batch_size": batch_size,
        }))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/cleanup/policies")
async def create_cleanup_policy(request: CreateCleanupPolicyRequest) -> Dict[str, Any]:
    """Create a cleanup policy."""
    session = _get_session()
    try:
        from common_lib.modules.notification.workers.models import CleanupPolicy
        from datetime import datetime
        policy = CleanupPolicy(
            name=request.name, target=request.target,
            retention_days=request.retention_days,
            schedule_cron=request.schedule_cron,
        )
        session.add(policy)
        session.commit()
        session.refresh(policy)
        return {"id": policy.id, "name": policy.name, "target": policy.target}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/cleanup/policies")
async def list_cleanup_policies() -> Dict[str, Any]:
    """List all cleanup policies."""
    session = _get_session()
    try:
        from common_lib.modules.notification.workers.models import CleanupPolicy
        from sqlmodel import select
        policies = session.exec(select(CleanupPolicy).order_by(CleanupPolicy.name)).all()
        return {"policies": [
            {
                "id": p.id, "name": p.name, "target": p.target,
                "retention_days": p.retention_days,
                "enabled": p.enabled,
                "schedule_cron": p.schedule_cron,
                "last_run_at": p.last_run_at.isoformat() if p.last_run_at else None,
            }
            for p in policies
        ]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ── Task Management Routes ──────────────────────────────────────────


@router.get("/tasks")
async def list_tasks(worker_type: Optional[str] = Query(None),
                      queue_name: Optional[str] = Query(None),
                      status: Optional[str] = Query(None),
                      limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    """List worker tasks with optional filters."""
    session = _get_session()
    try:
        svc = _get_task_svc(session)
        tasks = svc.list_tasks(
            worker_type=worker_type, queue_name=queue_name,
            status=status, limit=limit,
        )
        return {"tasks": tasks, "count": len(tasks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/stats")
async def get_worker_stats(worker_type: str = Query("delivery")) -> Dict[str, Any]:
    """Get pending task count for a worker type."""
    session = _get_session()
    try:
        svc = _get_task_svc(session)
        pending = svc.count_pending(worker_type=worker_type)
        return {"worker_type": worker_type, "pending_count": pending}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
