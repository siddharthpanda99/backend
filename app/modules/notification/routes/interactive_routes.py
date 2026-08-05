"""Interactive routes — Interactive action buttons, callback recording, stats."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional

from app.modules.project_management.deps import get_pm_session

router = APIRouter(prefix="/interactive", tags=["Notification — Interactive"])


class ActionCreateRequest(BaseModel):
    notification_id: str
    label: str
    action_type: str = "button"
    style: str = "primary"
    url: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    confirmation_text: Optional[str] = None


class CallbackRecordRequest(BaseModel):
    action_id: str
    notification_id: str
    recipient_id: str
    status: str = "clicked"
    action_type: str = "button"


@router.post("/actions")
async def create_action(request: ActionCreateRequest,
                         session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.interactive.service import InteractiveService
        svc = InteractiveService(session=session)
        return svc.create_action(
            notification_id=request.notification_id, label=request.label,
            action_type=request.action_type, style=request.style,
            url=request.url, payload=request.payload,
            confirmation_text=request.confirmation_text,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actions/{notification_id}")
async def get_actions(notification_id: str, session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.interactive.service import InteractiveService
        svc = InteractiveService(session=session)
        return {"actions": svc.get_actions(notification_id=notification_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/callbacks")
async def record_callback(request: CallbackRecordRequest,
                           session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.interactive.service import InteractiveService
        svc = InteractiveService(session=session)
        return svc.record_callback(
            action_id=request.action_id,
            notification_id=request.notification_id,
            recipient_id=request.recipient_id,
            status=request.status, action_type=request.action_type,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{notification_id}")
async def get_action_stats(notification_id: str,
                            session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.interactive.service import InteractiveService
        svc = InteractiveService(session=session)
        return svc.get_action_stats(notification_id=notification_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
