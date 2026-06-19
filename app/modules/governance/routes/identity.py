from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from datetime import datetime
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import GovernanceIdentity
import json

router = APIRouter(prefix="/identity", tags=["Governance - Identity"])


class IdentityCreate(BaseModel):
    agent_id: str
    name: str = ""
    owner: str = ""
    department: str = ""
    agent_type: str = "service"
    status: str = "draft"
    risk_level: str = "medium"
    capabilities: list[str] = []
    tools_allowed: list[str] = []
    compliance_tags: list[str] = []


class IdentityUpdate(BaseModel):
    name: str = ""
    owner: str = ""
    department: str = ""
    agent_type: str = ""
    status: str = ""
    risk_level: str = ""
    capabilities: list[str] | None = None
    tools_allowed: list[str] | None = None
    compliance_tags: list[str] | None = None


class StatusTransition(BaseModel):
    status: str


def _gov_to_dict(g: GovernanceIdentity) -> dict:
    return {
        "id": g.id,
        "subject_id": g.subject_id,
        "agent_id": g.subject_id,
        "display_name": g.display_name,
        "name": g.display_name,
        "subject_type": g.subject_type,
        "email": g.email,
        "tenant_id": g.tenant_id,
        "is_active": g.is_active,
        "status": "active" if g.is_active else "inactive",
        "capabilities": json.loads(g.capabilities_json) if g.capabilities_json else [],
        "compliance_tags": json.loads(g.compliance_tags_json)
        if g.compliance_tags_json
        else [],
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }


@router.get("")
def list_identities(session: Session = Depends(get_session)):
    identities = session.exec(select(GovernanceIdentity)).all()
    return [_gov_to_dict(i) for i in identities]


@router.post("")
def create_identity(body: IdentityCreate, session: Session = Depends(get_session)):
    existing = session.exec(
        select(GovernanceIdentity).where(GovernanceIdentity.subject_id == body.agent_id)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Identity already exists")

    gov = GovernanceIdentity(
        subject_id=body.agent_id,
        subject_type=body.agent_type,
        display_name=body.name,
        is_active=(body.status == "active"),
        capabilities_json=json.dumps(body.capabilities),
        compliance_tags_json=json.dumps(body.compliance_tags),
        tenant_id="default",
    )
    session.add(gov)
    session.commit()
    session.refresh(gov)
    return _gov_to_dict(gov)


@router.get("/{agent_id}")
def get_identity(agent_id: str, session: Session = Depends(get_session)):
    gov = session.exec(
        select(GovernanceIdentity).where(GovernanceIdentity.subject_id == agent_id)
    ).first()
    if not gov:
        raise HTTPException(status_code=404, detail="Identity not found")
    return _gov_to_dict(gov)


@router.put("/{agent_id}")
def update_identity(
    agent_id: str, body: IdentityUpdate, session: Session = Depends(get_session)
):
    gov = session.exec(
        select(GovernanceIdentity).where(GovernanceIdentity.subject_id == agent_id)
    ).first()
    if not gov:
        raise HTTPException(status_code=404, detail="Identity not found")

    if body.name != "":
        gov.display_name = body.name
    if body.agent_type != "":
        gov.subject_type = body.agent_type
    if body.status != "":
        gov.is_active = body.status == "active"
    if body.capabilities is not None:
        gov.capabilities_json = json.dumps(body.capabilities)
    if body.compliance_tags is not None:
        gov.compliance_tags_json = json.dumps(body.compliance_tags)
    gov.updated_at = datetime.utcnow()

    session.add(gov)
    session.commit()
    session.refresh(gov)
    return _gov_to_dict(gov)


@router.delete("/{agent_id}")
def delete_identity(agent_id: str, session: Session = Depends(get_session)):
    gov = session.exec(
        select(GovernanceIdentity).where(GovernanceIdentity.subject_id == agent_id)
    ).first()
    if not gov:
        raise HTTPException(status_code=404, detail="Identity not found")
    session.delete(gov)
    session.commit()
    return {"success": True}


@router.post("/{agent_id}/transition")
def transition_identity(
    agent_id: str, body: StatusTransition, session: Session = Depends(get_session)
):
    gov = session.exec(
        select(GovernanceIdentity).where(GovernanceIdentity.subject_id == agent_id)
    ).first()
    if not gov:
        raise HTTPException(status_code=404, detail="Identity not found")
    gov.is_active = body.status == "active"
    gov.updated_at = datetime.utcnow()
    session.add(gov)
    session.commit()
    session.refresh(gov)
    return _gov_to_dict(gov)
