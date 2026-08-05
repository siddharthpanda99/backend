"""Schedule routes — Notification scheduling, dispatch, recurring schedules."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from app.modules.project_management.deps import get_pm_session

router = APIRouter(prefix="/schedules", tags=["Notification — Scheduling"])


class ScheduleCreateRequest(BaseModel):
    notification_type: str
    recipient_id: str
    template_id: str
    scheduled_for: str  # ISO-8601
    channel: str = "email"
    timezone: str = "UTC"
    priority: str = "medium"


class RecurringCreateRequest(BaseModel):
    name: str
    notification_type: str
    template_id: str
    schedule_type: str = "cron"
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    channel: str = "email"
    recipient_ids: Optional[List[str]] = None
    timezone: str = "UTC"
    variables: Optional[Dict[str, Any]] = None


@router.get("/pending")
async def list_pending(session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session=session)
        return {"scheduled": svc.list_pending()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def schedule_notification(request: ScheduleCreateRequest,
                                 session=Depends(get_pm_session)):
    from datetime import datetime
    try:
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session=session)
        dt = datetime.fromisoformat(request.scheduled_for)
        return svc.schedule_notification(
            notification_type=request.notification_type,
            recipient_id=request.recipient_id,
            template_id=request.template_id,
            scheduled_for=dt, channel=request.channel,
            timezone=request.timezone, priority=request.priority,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dispatch")
async def dispatch_due(limit: int = 100, session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session=session)
        return {"dispatched": svc.dispatch_due(limit=limit), "count": limit}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{schedule_id}/cancel")
async def cancel_scheduled(schedule_id: str, session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session=session)
        result = svc.cancel_scheduled(schedule_id=schedule_id)
        if not result:
            raise HTTPException(status_code=404, detail="Schedule not found or already dispatched")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recurring")
async def create_recurring(request: RecurringCreateRequest,
                            session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session=session)
        return svc.create_recurring(
            name=request.name, notification_type=request.notification_type,
            template_id=request.template_id, schedule_type=request.schedule_type,
            cron_expression=request.cron_expression,
            interval_seconds=request.interval_seconds,
            channel=request.channel, timezone=request.timezone,
            recipient_ids=request.recipient_ids, variables=request.variables,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recurring")
async def list_recurring(active_only: bool = True,
                          session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session=session)
        return {"schedules": svc.list_recurring(active_only=active_only)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recurring/{schedule_id}/pause")
async def pause_recurring(schedule_id: str, session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session=session)
        result = svc.pause_recurring(schedule_id=schedule_id)
        if not result:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return {"success": True, "status": "paused"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recurring/{schedule_id}/resume")
async def resume_recurring(schedule_id: str, session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session=session)
        result = svc.resume_recurring(schedule_id=schedule_id)
        if not result:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return {"success": True, "status": "active"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
