from fastapi import APIRouter
from pydantic import BaseModel
from common_lib.modules.governance.incidents.service import get_incident_service

router = APIRouter(prefix="/incidents", tags=["Governance - Incidents"])


class IncidentCreate(BaseModel):
    incident_type: str
    severity: str = "medium"
    agent_id: str
    description: str = ""


@router.get("")
def list_incidents():
    svc = get_incident_service()
    items = svc.list_incidents()
    result = []
    for item in items:
        d = {"incident_id": getattr(item, "incident_id", "")}
        for attr in [
            "incident_type",
            "severity",
            "agent_id",
            "description",
            "status",
            "containment_action",
            "detected_at",
            "remediated_at",
        ]:
            if hasattr(item, attr):
                d[attr] = getattr(item, attr)
        result.append(d)
    return result


@router.post("")
def create_incident(body: IncidentCreate):
    svc = get_incident_service()
    item = svc.create(
        body.incident_type, body.severity, body.agent_id, body.description
    )
    d = {"incident_id": getattr(item, "incident_id", "")}
    for attr in [
        "incident_type",
        "severity",
        "agent_id",
        "description",
        "status",
        "containment_action",
        "detected_at",
        "remediaton_at",
    ]:
        if hasattr(item, attr):
            d[attr] = getattr(item, attr)
    return d


@router.post("/{incident_id}/{status}")
def update_incident_status(incident_id: str, status: str):
    svc = get_incident_service()
    if status in ("contain", "contained"):
        svc.contain(incident_id)
    elif status == "remediated":
        svc.remediate(incident_id)
    elif status == "recovered":
        svc.recover(incident_id)
    elif status == "closed":
        svc.close(incident_id)
    item = svc.get(incident_id)
    d = {"incident_id": incident_id, "status": status}
    if item:
        for attr in [
            "incident_type",
            "severity",
            "agent_id",
            "description",
            "containment_action",
            "detected_at",
            "remediaton_at",
        ]:
            if hasattr(item, attr):
                d[attr] = getattr(item, attr)
    return d
