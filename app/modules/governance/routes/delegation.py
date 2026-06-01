from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from common_lib.modules.governance.rbac.service import get_rbac_service
from common_lib.modules.governance.models.permissions import Delegation

router = APIRouter(prefix="/delegations", tags=["Governance - Delegation"])


class DelegationCreate(BaseModel):
    delegation_id: str
    delegating_agent: str
    delegatee_agent: str
    task_id: str = ""
    permissions_granted: list[str] = []
    constraints: dict = {}
    expires_at: str = ""
    max_invocations: int = 0


@router.get("")
def list_delegations():
    svc = get_rbac_service()
    items = []
    if hasattr(svc, "_delegations"):
        items = list(svc._delegations.values())
    result = []
    for d in items:
        entry = {}
        for attr in [
            "delegation_id",
            "delegating_agent",
            "delegatee_agent",
            "task_id",
            "permissions_granted",
            "constraints",
            "created_at",
            "expires_at",
            "max_invocations",
            "invocation_count",
            "revoked",
        ]:
            if hasattr(d, attr):
                entry[attr] = getattr(d, attr)
        result.append(entry)
    return result


@router.post("")
def create_delegation(body: DelegationCreate):
    svc = get_rbac_service()
    delegation = Delegation(
        delegation_id=body.delegation_id,
        delegating_agent=body.delegating_agent,
        delegatee_agent=body.delegatee_agent,
        task_id=body.task_id,
        permissions_granted=body.permissions_granted,
        constraints=body.constraints,
        expires_at=body.expires_at,
        max_invocations=body.max_invocations,
    )
    result = svc.create_delegation(delegation)
    d = {}
    for attr in [
        "delegation_id",
        "delegating_agent",
        "delegatee_agent",
        "task_id",
        "permissions_granted",
        "constraints",
        "created_at",
        "expires_at",
        "max_invocations",
        "invocation_count",
        "revoked",
    ]:
        if hasattr(result, attr):
            d[attr] = getattr(result, attr)
    return d


@router.post("/{delegation_id}/revoke")
def revoke_delegation(delegation_id: str):
    svc = get_rbac_service()
    success = svc.revoke_delegation(delegation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Delegation not found")
    return {"success": True}


@router.get("/check")
def check_delegation(agent_id: str, task_id: str):
    svc = get_rbac_service()
    result = svc.check_delegation(agent_id, task_id)
    if not result:
        return {"active": False}
    d = {
        "active": not result.revoked
        and not result.is_expired()
        and not result.is_exhausted()
    }
    for attr in [
        "delegation_id",
        "delegating_agent",
        "delegatee_agent",
        "task_id",
        "permissions_granted",
        "expires_at",
        "max_invocations",
        "invocation_count",
    ]:
        if hasattr(result, attr):
            d[attr] = getattr(result, attr)
    return d
