from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import GovernanceIncident
import json

router = APIRouter(prefix="/incidents", tags=["Governance - Incidents"])


class IncidentCreate(BaseModel):
    incident_type: str
    severity: str = "medium"
    agent_id: str
    description: str = ""


def _incident_to_dict(i: GovernanceIncident) -> dict:
    return {
        "incident_id": i.id,
        "title": i.title,
        "description": i.description,
        "severity": i.severity,
        "incident_type": i.incident_type,
        "status": i.status,
        "agent_id": i.reported_by,
        "reported_by": i.reported_by,
        "assigned_to": i.assigned_to,
        "detected_at": i.created_at.isoformat() if i.created_at else None,
        "remediated_at": i.resolved_at.isoformat() if i.resolved_at else None,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }


@router.get("")
def list_incidents(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceIncident)).all()
    return [_incident_to_dict(i) for i in items]


@router.post("")
def create_incident(body: IncidentCreate, session: Session = Depends(get_session)):
    incident = GovernanceIncident(
        title=f"{body.incident_type} - {body.agent_id}",
        description=body.description,
        severity=body.severity,
        incident_type=body.incident_type,
        status="open",
        reported_by=body.agent_id,
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return _incident_to_dict(incident)


@router.post("/{incident_id}/{status}")
def update_incident_status(
    incident_id: int, status: str, session: Session = Depends(get_session)
):
    incident = session.exec(
        select(GovernanceIncident).where(GovernanceIncident.id == incident_id)
    ).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    valid_transitions = {"contain", "contained", "remediated", "recovered", "closed"}
    if status in valid_transitions:
        if status in ("contain", "contained"):
            incident.status = "contained"
        elif status == "remediated":
            incident.status = "remediated"
            incident.resolved_at = datetime.utcnow()
        elif status == "recovered":
            incident.status = "recovered"
        elif status == "closed":
            incident.status = "closed"
        incident.updated_at = datetime.utcnow()
        session.add(incident)
        session.commit()
        session.refresh(incident)

    return _incident_to_dict(incident)
