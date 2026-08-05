"""Rule routes — Conditional notification rules, segment management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from app.modules.project_management.deps import get_pm_session

router = APIRouter(prefix="/rules", tags=["Notification — Rules & Segments"])


class RuleCreateRequest(BaseModel):
    name: str
    event_type: str
    conditions: List[Dict[str, Any]]
    actions: Optional[Dict[str, Any]] = None
    match_all: bool = True


class EvaluateRequest(BaseModel):
    event_type: str
    context: Dict[str, Any]


class SegmentCreateRequest(BaseModel):
    name: str
    criteria: Dict[str, Any]
    recipient_ids: Optional[List[str]] = None
    dynamic: bool = True


@router.get("/")
async def list_rules(event_type: Optional[str] = None,
                      session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session=session)
        return {"rules": svc.list_rules(event_type=event_type)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_rule(request: RuleCreateRequest,
                       session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session=session)
        return svc.create_rule(
            name=request.name, event_type=request.event_type,
            conditions=request.conditions, actions=request.actions or {},
            match_all=request.match_all,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate")
async def evaluate_rules(request: EvaluateRequest,
                          session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session=session)
        return {"matches": svc.evaluate(event_type=request.event_type, context=request.context)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str, session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session=session)
        result = svc.delete_rule(rule_id=rule_id)
        if not result:
            raise HTTPException(status_code=404, detail="Rule not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/segments")
async def list_segments(session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session=session)
        return {"segments": svc.list_segments()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/segments")
async def create_segment(request: SegmentCreateRequest,
                          session=Depends(get_pm_session)):
    try:
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session=session)
        return svc.create_segment(
            name=request.name, criteria=request.criteria,
            recipient_ids=request.recipient_ids, dynamic=request.dynamic,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
