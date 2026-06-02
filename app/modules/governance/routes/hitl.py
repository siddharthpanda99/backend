from fastapi import APIRouter, HTTPException
from typing import Any
from pydantic import BaseModel, Field
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
    source: str = "manual"
    session_id: str = ""
    trace_id: str = ""
    tool_input: dict[str, Any] = Field(default_factory=dict)


class ApproveDenyRequest(BaseModel):
    decided_by: str
    notes: str = ""


class ModifyRequest(ApproveDenyRequest):
    tool_input: dict[str, Any] = Field(default_factory=dict)


class ExecuteRequest(BaseModel):
    outcome: str = "Execution resumed"


class FeedbackRequest(BaseModel):
    rating: str
    comment: str = ""


class CreateOverride(BaseModel):
    target: str
    target_type: str
    action: str
    reason: str
    authorized_by: str
    incident_id: str = ""


REQUEST_ATTRS = [
    "approval_policy_id", "agent_id", "action", "tool", "risk_score",
    "justification", "route_to", "requested_at", "expires_at", "decided_by",
    "decided_at", "decision_notes", "approval_token", "source", "session_id",
    "trace_id", "tool_input", "modified_tool_input", "executed_at",
    "execution_outcome", "feedback_rating", "feedback_comment", "timeline",
]


def _serialize_request(item):
    result = {"id": getattr(item, "id", ""), "status": getattr(item, "status", "pending")}
    for attr in REQUEST_ATTRS:
        if hasattr(item, attr):
            result[attr] = getattr(item, attr)
    return result


@router.get("/requests")
def list_requests():
    svc = get_hitl_service()
    items = svc.list_requests()
    return [_serialize_request(item) for item in items]


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
        body.source,
        body.session_id,
        body.trace_id,
        body.tool_input,
    )
    return _serialize_request(item)


@router.get("/requests/{request_id}")
def get_request(request_id: str):
    item = get_hitl_service().get_request(request_id)
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")
    return _serialize_request(item)


@router.post("/requests/{request_id}/approve")
def approve_request(request_id: str, body: ApproveDenyRequest):
    svc = get_hitl_service()
    if not svc.approve(request_id, body.decided_by, body.notes):
        raise HTTPException(status_code=409, detail="Request is missing, expired, or already decided")
    return _serialize_request(svc.get_request(request_id))


@router.post("/requests/{request_id}/deny")
def deny_request(request_id: str, body: ApproveDenyRequest):
    svc = get_hitl_service()
    if not svc.deny(request_id, body.decided_by, body.notes):
        raise HTTPException(status_code=409, detail="Request is missing or already decided")
    return _serialize_request(svc.get_request(request_id))


@router.post("/requests/{request_id}/modify")
def modify_request(request_id: str, body: ModifyRequest):
    svc = get_hitl_service()
    if not svc.modify(request_id, body.decided_by, body.tool_input, body.notes):
        raise HTTPException(status_code=409, detail="Request is missing or already decided")
    return _serialize_request(svc.get_request(request_id))


@router.post("/requests/{request_id}/execute")
def execute_request(request_id: str, body: ExecuteRequest):
    svc = get_hitl_service()
    if not svc.execute(request_id, body.outcome):
        raise HTTPException(status_code=409, detail="Request has not been approved")
    return _serialize_request(svc.get_request(request_id))


@router.post("/requests/{request_id}/feedback")
def add_feedback(request_id: str, body: FeedbackRequest):
    svc = get_hitl_service()
    if body.rating not in ("good", "bad", "improve"):
        raise HTTPException(status_code=422, detail="rating must be good, bad, or improve")
    if not svc.add_feedback(request_id, body.rating, body.comment):
        raise HTTPException(status_code=404, detail="Request not found")
    return _serialize_request(svc.get_request(request_id))


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


@router.post("/reload")
def reload_seed_data():
    svc = get_hitl_service()
    svc._load_seed_data(force=True)
    return {
        "status": "success",
        "policies_count": len(svc.list_approval_policies()),
        "requests_count": len(svc.list_requests()),
        "overrides_count": len(svc.list_overrides()),
    }
