from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from common_lib.modules.governance.rbac.service import get_rbac_service
from common_lib.modules.governance.models.permissions import RoleAssignment

router = APIRouter(prefix="/role-assignments", tags=["Governance - Role Assignments"])


class AssignmentCreate(BaseModel):
    id: str = ""
    principal_type: str = "agent"
    principal_id: str
    role: str
    granted_by: str = ""
    granted_at: str = ""
    expires_at: str = ""
    scope_override: dict = {}
    justification: str = ""
    status: str = "active"


@router.get("")
def list_assignments():
    svc = get_rbac_service()
    items = []
    if hasattr(svc, "_assignments"):
        items = list(svc._assignments.values())
    result = []
    for a in items:
        entry = {}
        for attr in [
            "id",
            "principal_type",
            "principal_id",
            "role",
            "granted_by",
            "granted_at",
            "expires_at",
            "scope_override",
            "justification",
            "status",
        ]:
            if hasattr(a, attr):
                entry[attr] = getattr(a, attr)
        result.append(entry)
    return result


@router.post("")
def create_assignment(body: AssignmentCreate):
    svc = get_rbac_service()
    assignment = RoleAssignment(
        id=body.id,
        principal_type=body.principal_type,
        principal_id=body.principal_id,
        role=body.role,
        granted_by=body.granted_by,
        granted_at=body.granted_at,
        expires_at=body.expires_at,
        scope_override=body.scope_override,
        justification=body.justification,
        status=body.status,
    )
    result = svc.assign_role(assignment)
    d = {}
    for attr in [
        "id",
        "principal_type",
        "principal_id",
        "role",
        "granted_by",
        "granted_at",
        "expires_at",
        "scope_override",
        "justification",
        "status",
    ]:
        if hasattr(result, attr):
            d[attr] = getattr(result, attr)
    return d


@router.delete("/{assignment_id}")
def revoke_assignment(assignment_id: str):
    svc = get_rbac_service()
    success = svc.revoke_assignment(assignment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {"success": True}


@router.get("/agent/{agent_id}")
def get_agent_roles(agent_id: str):
    svc = get_rbac_service()
    roles = svc.get_roles_for_agent(agent_id)
    permissions = []
    try:
        permissions = [p.to_dict() for p in svc.get_permissions_for_agent(agent_id)]
    except Exception:
        pass
    return {"agent_id": agent_id, "roles": roles, "permissions": permissions}
