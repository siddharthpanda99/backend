from fastapi import APIRouter, HTTPException, Depends
from typing import Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import (
    GovernanceApprovalRequest,
    GovernanceEmergencyOverride,
)
import json
import uuid

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


def _request_to_dict(r: GovernanceApprovalRequest) -> dict:
    return {
        "id": r.request_id,
        "approval_policy_id": r.approval_policy_id,
        "agent_id": r.agent_id,
        "action": r.action,
        "tool": r.tool,
        "risk_score": r.risk_score,
        "justification": r.justification,
        "route_to": r.route_to,
        "requested_at": r.requested_at,
        "expires_at": r.expires_at,
        "status": r.status,
        "decision": r.decision,
        "decided_by": r.decided_by,
        "decided_at": r.decided_at,
        "decision_notes": r.decision_notes,
        "approval_token": r.approval_token,
        "source": r.source,
        "session_id": r.session_id,
        "trace_id": r.trace_id,
        "tool_input": json.loads(r.tool_input) if r.tool_input else {},
        "modified_tool_input": json.loads(r.modified_tool_input)
        if r.modified_tool_input
        else None,
        "executed_at": r.executed_at,
        "execution_outcome": r.execution_outcome,
        "feedback_rating": r.feedback_rating,
        "feedback_comment": r.feedback_comment,
        "timeline": json.loads(r.timeline) if r.timeline else [],
    }


def _override_to_dict(o: GovernanceEmergencyOverride) -> dict:
    return {
        "target": o.target,
        "target_type": o.target_type,
        "action": o.action,
        "reason": o.reason,
        "authorized_by": o.authorized_by,
        "incident_id": o.incident_id,
        "created_at": o.created_at.isoformat() if o.created_at else "",
    }


def _gen_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


def _now_str() -> str:
    return datetime.utcnow().isoformat()


@router.get("/requests")
def list_requests(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceApprovalRequest)).all()
    return [_request_to_dict(r) for r in items]


@router.post("/requests")
def create_request(body: CreateRequest, session: Session = Depends(get_session)):
    now = _now_str()
    rid = _gen_id()
    token = uuid.uuid4().hex[:16]
    req = GovernanceApprovalRequest(
        request_id=rid,
        approval_policy_id=body.approval_policy_id,
        agent_id=body.agent_id,
        action=body.action,
        tool=body.tool,
        risk_score=body.risk_score,
        justification=body.justification,
        route_to=body.route_to,
        source=body.source,
        session_id=body.session_id,
        trace_id=body.trace_id,
        tool_input=json.dumps(body.tool_input),
        requested_at=now,
        expires_at=(datetime.utcnow() + timedelta(minutes=5)).isoformat(),
        status="pending",
        approval_token=token,
        timeline=json.dumps([{"action": "created", "at": now}]),
    )
    session.add(req)
    session.commit()
    session.refresh(req)
    return _request_to_dict(req)


@router.get("/requests/{request_id}")
def get_request(request_id: str, session: Session = Depends(get_session)):
    r = session.exec(
        select(GovernanceApprovalRequest).where(
            GovernanceApprovalRequest.request_id == request_id
        )
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found")
    return _request_to_dict(r)


@router.post("/requests/{request_id}/approve")
def approve_request(
    request_id: str, body: ApproveDenyRequest, session: Session = Depends(get_session)
):
    r = session.exec(
        select(GovernanceApprovalRequest).where(
            GovernanceApprovalRequest.request_id == request_id
        )
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found")
    if r.status != "pending":
        raise HTTPException(status_code=409, detail="Request is not pending")
    now = _now_str()
    r.status = "approved"
    r.decided_by = body.decided_by
    r.decided_at = now
    r.decision_notes = body.notes
    r.decision = "approved"
    timeline = json.loads(r.timeline) if r.timeline else []
    timeline.append({"action": "approved", "by": body.decided_by, "at": now})
    r.timeline = json.dumps(timeline)
    session.add(r)
    session.commit()
    session.refresh(r)
    return _request_to_dict(r)


@router.post("/requests/{request_id}/deny")
def deny_request(
    request_id: str, body: ApproveDenyRequest, session: Session = Depends(get_session)
):
    r = session.exec(
        select(GovernanceApprovalRequest).where(
            GovernanceApprovalRequest.request_id == request_id
        )
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found")
    if r.status != "pending":
        raise HTTPException(status_code=409, detail="Request is not pending")
    now = _now_str()
    r.status = "denied"
    r.decided_by = body.decided_by
    r.decided_at = now
    r.decision_notes = body.notes
    r.decision = "denied"
    timeline = json.loads(r.timeline) if r.timeline else []
    timeline.append({"action": "denied", "by": body.decided_by, "at": now})
    r.timeline = json.dumps(timeline)
    session.add(r)
    session.commit()
    session.refresh(r)
    return _request_to_dict(r)


@router.post("/requests/{request_id}/modify")
def modify_request(
    request_id: str, body: ModifyRequest, session: Session = Depends(get_session)
):
    r = session.exec(
        select(GovernanceApprovalRequest).where(
            GovernanceApprovalRequest.request_id == request_id
        )
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found")
    if r.status != "pending":
        raise HTTPException(status_code=409, detail="Request is not pending")
    now = _now_str()
    r.modified_tool_input = json.dumps(body.tool_input)
    r.status = "modified"
    r.decided_by = body.decided_by
    r.decided_at = now
    r.decision_notes = body.notes
    r.decision = "modified"
    timeline = json.loads(r.timeline) if r.timeline else []
    timeline.append(
        {
            "action": "modified",
            "by": body.decided_by,
            "at": now,
            "tool_input_modified": True,
        }
    )
    r.timeline = json.dumps(timeline)
    session.add(r)
    session.commit()
    session.refresh(r)
    return _request_to_dict(r)


@router.post("/requests/{request_id}/execute")
def execute_request(
    request_id: str, body: ExecuteRequest, session: Session = Depends(get_session)
):
    r = session.exec(
        select(GovernanceApprovalRequest).where(
            GovernanceApprovalRequest.request_id == request_id
        )
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found")
    if r.status not in ("approved", "modified"):
        raise HTTPException(status_code=409, detail="Request has not been approved")
    now = _now_str()
    r.status = "executed"
    r.executed_at = now
    r.execution_outcome = body.outcome
    timeline = json.loads(r.timeline) if r.timeline else []
    timeline.append({"action": "executed", "at": now, "outcome": body.outcome})
    r.timeline = json.dumps(timeline)
    session.add(r)
    session.commit()
    session.refresh(r)
    return _request_to_dict(r)


@router.post("/requests/{request_id}/feedback")
def add_feedback(
    request_id: str, body: FeedbackRequest, session: Session = Depends(get_session)
):
    if body.rating not in ("good", "bad", "improve"):
        raise HTTPException(
            status_code=422, detail="rating must be good, bad, or improve"
        )
    r = session.exec(
        select(GovernanceApprovalRequest).where(
            GovernanceApprovalRequest.request_id == request_id
        )
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found")
    r.feedback_rating = body.rating
    r.feedback_comment = body.comment
    timeline = json.loads(r.timeline) if r.timeline else []
    timeline.append({"action": "feedback", "rating": body.rating, "at": _now_str()})
    r.timeline = json.dumps(timeline)
    session.add(r)
    session.commit()
    session.refresh(r)
    return _request_to_dict(r)


@router.get("/overrides")
def list_overrides(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceEmergencyOverride)).all()
    return [_override_to_dict(o) for o in items]


@router.post("/overrides")
def create_override(body: CreateOverride, session: Session = Depends(get_session)):
    override = GovernanceEmergencyOverride(
        target=body.target,
        target_type=body.target_type,
        action=body.action,
        reason=body.reason,
        authorized_by=body.authorized_by,
        incident_id=body.incident_id,
    )
    session.add(override)
    session.commit()
    session.refresh(override)
    return _override_to_dict(override)


@router.post("/reload")
def reload_seed_data(session: Session = Depends(get_session)):
    requests = session.exec(select(GovernanceApprovalRequest)).all()
    overrides = session.exec(select(GovernanceEmergencyOverride)).all()
    return {
        "status": "success",
        "policies_count": len(requests),
        "requests_count": len(requests),
        "overrides_count": len(overrides),
    }
