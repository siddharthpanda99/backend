from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from common_lib.modules.governance.identity.service import get_identity_service
from common_lib.modules.governance.models.identity import AgentIdentity

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


@router.get("")
def list_identities():
    svc = get_identity_service()
    return [i.to_dict() for i in svc.list_active()]


@router.post("")
def create_identity(body: IdentityCreate):
    svc = get_identity_service()
    identity = AgentIdentity(
        agent_id=body.agent_id,
        name=body.name,
        owner=body.owner,
        department=body.department,
        agent_type=body.agent_type,
        status=body.status,
        risk_level=body.risk_level,
        capabilities=body.capabilities,
        tools_allowed=body.tools_allowed,
        compliance_tags=body.compliance_tags,
    )
    result = svc.register(identity)
    return result.to_dict()


@router.get("/{agent_id}")
def get_identity(agent_id: str):
    svc = get_identity_service()
    result = svc.get(agent_id)
    if not result:
        raise HTTPException(status_code=404, detail="Identity not found")
    return result.to_dict()


@router.put("/{agent_id}")
def update_identity(agent_id: str, body: IdentityUpdate):
    svc = get_identity_service()
    existing = svc.get(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Identity not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        if val is not None and hasattr(existing, field):
            setattr(existing, field, val)
    svc.update(existing)
    return existing.to_dict()


@router.delete("/{agent_id}")
def delete_identity(agent_id: str):
    svc = get_identity_service()
    existing = svc.get(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Identity not found")
    svc.revoke(agent_id)
    return {"success": True}


@router.post("/{agent_id}/transition")
def transition_identity(agent_id: str, body: StatusTransition):
    svc = get_identity_service()
    success = svc.transition(agent_id, body.status)
    if not success:
        raise HTTPException(status_code=400, detail="Transition failed")
    result = svc.get(agent_id)
    return result.to_dict() if result else {"success": True}
