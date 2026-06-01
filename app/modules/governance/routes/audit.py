from fastapi import APIRouter
from pydantic import BaseModel
from common_lib.modules.governance.audit.service import get_audit_service
from common_lib.modules.governance.models.audit import AuditEvent
import datetime
import uuid

router = APIRouter(prefix="/audit", tags=["Governance - Audit"])

class AuditEventCreate(BaseModel):
    action: str
    agent_id: str
    resource: dict = {}
    outcome: dict = {}
    authz_decision: dict = {}
    event_type: str = "api"
    severity: str = "low"

@router.post("/events")
def create_audit_event(body: AuditEventCreate):
    svc = get_audit_service()
    evt = svc.record(
        event_type=body.event_type,
        severity=body.severity,
        agent_id=body.agent_id,
        action=body.action,
        resource=body.resource,
        authz_decision=body.authz_decision,
        outcome=body.outcome
    )
    return evt.to_dict()

@router.get("/events")
def list_audit_events():
    svc = get_audit_service()
    items = svc.list_events()
    result = []
    for item in items:
        d = {"event_id": getattr(item, "event_id", "")}
        for attr in [
            "event_type",
            "severity",
            "agent_id",
            "agent_name",
            "action",
            "resource",
            "environment",
            "authz_decision",
            "outcome",
            "trace_id",
            "timestamp",
            "prev_hash",
            "hash",
        ]:
            if hasattr(item, attr):
                d[attr] = getattr(item, attr)
        result.append(d)
    return result


@router.delete("/events")
def clear_audit_events():
    svc = get_audit_service()
    svc._events.clear() if hasattr(svc, "_events") else None
    return {"success": True}
