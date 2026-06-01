from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from common_lib.modules.governance.hitl.service import get_hitl_service

router = APIRouter(prefix="/hitl", tags=["Governance - HITL"])


class CreateRequest(BaseModel):
    approval_policy_id: str = ""
    agent_id: str
    action: str = ""
    tool: str = ""
    risk_score: int = 0
    justification: str = ""
    route_to: str = ""


class ApproveDenyRequest(BaseModel):
    decided_by: str
    notes: str = ""


class CreateOverride(BaseModel):
    target: str
    target_type: str
    action: str
    reason: str
    authorized_by: str
    incident_id: str = ""


@router.get("/requests")
def list_requests():
    svc = get_hitl_service()
    items = svc.list_requests()
    result = []
    for item in items:
        d = {
            "id": getattr(item, "request_id", getattr(item, "id", "")),
            "status": getattr(item, "status", "pending"),
        }
        for attr in [
            "approval_policy_id",
            "agent_id",
            "action",
            "tool",
            "risk_score",
            "justification",
            "route_to",
            "requested_at",
            "expires_at",
            "decided_by",
            "decided_at",
            "decision_notes",
            "approval_token",
        ]:
            if hasattr(item, attr):
                d[attr] = (
                    str(getattr(item, attr))
                    if not isinstance(
                        getattr(item, attr), (str, int, float, bool, type(None))
                    )
                    else getattr(item, attr)
                )
        result.append(d)
    return result


@router.post("/requests")
def create_request(body: CreateRequest):
    svc = get_hitl_service()
    item = svc.create_request(
        body.approval_policy_id,
        body.agent_id,
        body.action,
        body.tool,
        body.risk_score,
        body.justification,
        body.route_to,
    )
    d = {
        "id": getattr(item, "request_id", getattr(item, "id", "")),
        "status": getattr(item, "status", "pending"),
    }
    for attr in [
        "approval_policy_id",
        "agent_id",
        "action",
        "tool",
        "risk_score",
        "justification",
        "route_to",
        "requested_at",
        "expires_at",
        "decided_by",
        "decided_at",
        "decision_notes",
        "approval_token",
    ]:
        if hasattr(item, attr):
            d[attr] = (
                str(getattr(item, attr))
                if not isinstance(
                    getattr(item, attr), (str, int, float, bool, type(None))
                )
                else getattr(item, attr)
            )
    return d


@router.post("/requests/{request_id}/approve")
def approve_request(request_id: str, body: ApproveDenyRequest):
    svc = get_hitl_service()
    svc.approve(request_id, body.decided_by, body.notes)
    return {"success": True, "id": request_id, "status": "approved"}


@router.post("/requests/{request_id}/deny")
def deny_request(request_id: str, body: ApproveDenyRequest):
    svc = get_hitl_service()
    svc.deny(request_id, body.decided_by, body.notes)
    return {"success": True, "id": request_id, "status": "denied"}


@router.get("/overrides")
def list_overrides():
    svc = get_hitl_service()
    items = svc.list_overrides()
    result = []
    for item in items:
        d = {}
        for attr in [
            "target",
            "target_type",
            "action",
            "reason",
            "authorized_by",
            "incident_id",
            "created_at",
        ]:
            if hasattr(item, attr):
                v = getattr(item, attr)
                d[attr] = (
                    str(v)
                    if not isinstance(v, (str, int, float, bool, type(None)))
                    else v
                )
        result.append(d)
    return result


@router.post("/overrides")
def create_override(body: CreateOverride):
    svc = get_hitl_service()
    item = svc.emergency_override(
        body.target,
        body.target_type,
        body.action,
        body.reason,
        body.authorized_by,
        body.incident_id,
    )
    d = {}
    for attr in [
        "target",
        "target_type",
        "action",
        "reason",
        "authorized_by",
        "incident_id",
        "created_at",
    ]:
        if hasattr(item, attr):
            v = getattr(item, attr)
            d[attr] = (
                str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
            )
    return d
