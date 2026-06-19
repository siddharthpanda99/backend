import json
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import GovernanceAuditEvent

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
def create_audit_event(body: AuditEventCreate, session: Session = Depends(get_session)):
    event = GovernanceAuditEvent(
        event_type=body.event_type,
        subject_id=body.agent_id,
        action=body.action,
        resource_type=body.resource.get("type"),
        resource_id=body.resource.get("id"),
        outcome=body.outcome.get("status", "allowed"),
        details_json=json.dumps(
            {
                "severity": body.severity,
                "resource": body.resource,
                "outcome": body.outcome,
                "authz_decision": body.authz_decision,
            }
        ),
        created_at=datetime.utcnow(),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event.model_dump()


@router.get("/events")
def list_audit_events(session: Session = Depends(get_session)):
    items = session.exec(
        select(GovernanceAuditEvent).order_by(GovernanceAuditEvent.created_at.desc())
    ).all()
    return [item.model_dump() for item in items]


@router.delete("/events")
def clear_audit_events(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceAuditEvent)).all()
    for item in items:
        session.delete(item)
    session.commit()
    return {"success": True}
