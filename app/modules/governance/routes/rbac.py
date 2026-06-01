from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from common_lib.modules.governance.rbac.service import get_rbac_service
from common_lib.modules.governance.models.permissions import (
    RoleDefinition,
    Permission,
    Group,
)
from common_lib.modules.governance.rbac.roles import BUILTIN_ROLES

router = APIRouter(prefix="/rbac", tags=["Governance - RBAC"])


class RoleCreate(BaseModel):
    role_id: str
    name: str
    description: str = ""
    permissions: list[str] = []
    risk_ceiling: str = "high"
    min_trust_score: float = 0.0


class PermissionCreate(BaseModel):
    permission_id: str
    name: str = ""
    description: str = ""
    resource_type: str = "*"
    resource_pattern: str = "*"
    actions: list[str] = ["*"]
    deny_actions: list[str] = []


class GroupCreate(BaseModel):
    group_id: str
    name: str = ""
    description: str = ""
    roles: list[str] = []
    members: list[str] = []


class GroupUpdate(BaseModel):
    name: str = ""
    description: str = ""
    roles: list[str] | None = None
    members: list[str] | None = None


class AddMemberRequest(BaseModel):
    agent_id: str


@router.get("/roles")
def list_roles():
    svc = get_rbac_service()
    return [r.to_dict() for r in svc.list_roles()]


@router.post("/roles")
def create_role(body: RoleCreate):
    svc = get_rbac_service()
    role = RoleDefinition(
        role_id=body.role_id,
        name=body.name,
        description=body.description,
        permissions=body.permissions,
        risk_ceiling=body.risk_ceiling,
        min_trust_score=body.min_trust_score,
    )
    result = svc.define_role(role)
    return result.to_dict()


@router.delete("/roles/{role_id}")
def delete_role(role_id: str):
    svc = get_rbac_service()
    if role_id in BUILTIN_ROLES:
        raise HTTPException(status_code=400, detail="Cannot delete built-in role")
    result = svc.revoke_assignment(role_id)
    return {"success": True}


@router.get("/permissions")
def list_permissions():
    svc = get_rbac_service()
    return (
        [p.to_dict() for p in svc._permissions.values()]
        if hasattr(svc, "_permissions")
        else []
    )


@router.post("/permissions")
def create_permission(body: PermissionCreate):
    svc = get_rbac_service()
    perm = Permission(
        permission_id=body.permission_id,
        name=body.name,
        description=body.description,
        resource_type=body.resource_type,
        resource_pattern=body.resource_pattern,
        actions=body.actions,
        deny_actions=body.deny_actions,
    )
    result = svc.define_permission(perm)
    return result.to_dict()


@router.delete("/permissions/{perm_id}")
def delete_permission(perm_id: str):
    svc = get_rbac_service()
    return {"success": True}


@router.get("/groups")
def list_groups():
    svc = get_rbac_service()
    return (
        [g.to_dict() for g in svc._groups.values()] if hasattr(svc, "_groups") else []
    )


@router.post("/groups")
def create_group(body: GroupCreate):
    svc = get_rbac_service()
    group = Group(
        group_id=body.group_id,
        name=body.name,
        description=body.description,
        roles=body.roles,
        members=body.members,
    )
    result = svc.create_group(group)
    return result.to_dict()


@router.put("/groups/{group_id}")
def update_group(group_id: str, body: GroupUpdate):
    svc = get_rbac_service()
    existing = svc.get_group(group_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Group not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(existing, field, val)
    svc.create_group(existing)
    return existing.to_dict()


@router.delete("/groups/{group_id}")
def delete_group(group_id: str):
    svc = get_rbac_service()
    return {"success": True}


@router.post("/groups/{group_id}/members")
def add_to_group(group_id: str, body: AddMemberRequest):
    svc = get_rbac_service()
    svc.add_to_group(body.agent_id, group_id)
    return {"success": True}
