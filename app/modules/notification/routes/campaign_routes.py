"""Campaign routes — Broadcast campaign management with progress tracking."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from app.modules.project_management.deps import get_pm_session

router = APIRouter(prefix="/campaigns", tags=["Notification — Campaigns"])


class CampaignCreateRequest(BaseModel):
    name: str
    template_id: str
    audience_scope: str = "all"
    notification_type: str = "broadcast"
    priority: str = "medium"
    total_count: int = 0
    description: str = ""
    audience_filter: Optional[Dict[str, Any]] = None


class CampaignStatusRequest(BaseModel):
    status: str  # paused, active, cancelled


@router.get("/")
async def list_campaigns(status: Optional[str] = None,
                          session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session=session)
        return {"campaigns": svc.list_campaigns(status=status)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_campaign(request: CampaignCreateRequest,
                           session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session=session)
        return svc.create_campaign(
            name=request.name, template_id=request.template_id,
            audience_scope=request.audience_scope,
            notification_type=request.notification_type,
            priority=request.priority,
            total_count=request.total_count,
            description=request.description,
            audience_filter=request.audience_filter,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str, session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session=session)
        result = svc.get_campaign(campaign_id=campaign_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/progress")
async def get_campaign_progress(campaign_id: str,
                                 session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session=session)
        result = svc.get_progress(campaign_id=campaign_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{campaign_id}/status")
async def update_campaign_status(campaign_id: str,
                                  request: CampaignStatusRequest,
                                  session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session=session)
        result = svc.update_status(campaign_id=campaign_id, status=request.status)
        if result is None:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
