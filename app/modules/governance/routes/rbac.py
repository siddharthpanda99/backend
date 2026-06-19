import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import (
    GovernanceRole,
    GovernancePermission,
    GovernanceRoleAssignment,
    GovernanceDelegation,
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
def list_roles(session: Session = Depends(get_session)):
    roles = session.exec(select(GovernanceRole)).all()
    return [
        {
            "role_id": r.name,
            "name": r.name,
            "description": r.description or "",
            "permissions": json.loads(r.permissions_json) if r.permissions_json else [],
            "is_builtin": r.is_builtin,
        }
        for r in roles
    ]


@router.post("/roles")
def create_role(body: RoleCreate, session: Session = Depends(get_session)):
    existing = session.exec(
        select(GovernanceRole).where(GovernanceRole.name == body.role_id)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Role already exists")
    role = GovernanceRole(
        name=body.role_id,
        description=body.description,
        permissions_json=json.dumps(body.permissions),
        is_builtin=False,
    )
    session.add(role)
    session.commit()
    session.refresh(role)
    return {
        "role_id": role.name,
        "name": role.name,
        "description": role.description or "",
        "permissions": json.loads(role.permissions_json)
        if role.permissions_json
        else [],
        "is_builtin": role.is_builtin,
    }


@router.delete("/roles/{role_id}")
def delete_role(role_id: str, session: Session = Depends(get_session)):
    if role_id in BUILTIN_ROLES:
        raise HTTPException(status_code=400, detail="Cannot delete built-in role")
    role = session.exec(
        select(GovernanceRole).where(GovernanceRole.name == role_id)
    ).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    session.delete(role)
    session.commit()
    return {"success": True}


@router.get("/permissions")
def list_permissions(session: Session = Depends(get_session)):
    perms = session.exec(select(GovernancePermission)).all()
    return [
        {
            "permission_id": p.action,
            "name": p.action,
            "description": p.description or "",
            "resource_type": p.resource_type,
            "actions": [p.action],
        }
        for p in perms
    ]


@router.post("/permissions")
def create_permission(body: PermissionCreate, session: Session = Depends(get_session)):
    perm = GovernancePermission(
        action=body.permission_id,
        description=body.description,
        resource_type=body.resource_type,
        resource_id=body.resource_pattern,
    )
    session.add(perm)
    session.commit()
    session.refresh(perm)
    return {
        "permission_id": perm.action,
        "name": perm.action,
        "description": perm.description or "",
        "resource_type": perm.resource_type,
        "actions": [perm.action],
    }


@router.delete("/permissions/{perm_id}")
def delete_permission(perm_id: str, session: Session = Depends(get_session)):
    perm = session.exec(
        select(GovernancePermission).where(GovernancePermission.action == perm_id)
    ).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    session.delete(perm)
    session.commit()
    return {"success": True}


@router.get("/groups")
def list_groups(session: Session = Depends(get_session)):
    assignments = session.exec(select(GovernanceRoleAssignment)).all()
    groups: dict[str, dict] = {}
    for a in assignments:
        gid = a.subject_id
        if gid not in groups:
            groups[gid] = {
                "group_id": gid,
                "name": gid,
                "description": "",
                "roles": [],
                "members": [],
            }
        if a.role_name not in groups[gid]["roles"]:
            groups[gid]["roles"].append(a.role_name)
    return list(groups.values())


@router.post("/groups")
def create_group(body: GroupCreate, session: Session = Depends(get_session)):
    for role_name in body.roles:
        assignment = GovernanceRoleAssignment(
            subject_id=body.group_id,
            subject_type="group",
            role_name=role_name,
        )
        session.add(assignment)
    session.commit()
    return {
        "group_id": body.group_id,
        "name": body.name or body.group_id,
        "description": body.description,
        "roles": body.roles,
        "members": body.members,
        "is_builtin": False,
    }


@router.put("/groups/{group_id}")
def update_group(
    group_id: str, body: GroupUpdate, session: Session = Depends(get_session)
):
    existing_assignments = session.exec(
        select(GovernanceRoleAssignment).where(
            GovernanceRoleAssignment.subject_id == group_id
        )
    ).all()
    if not existing_assignments and not body.roles:
        raise HTTPException(status_code=404, detail="Group not found")
    if body.roles is not None:
        for a in existing_assignments:
            session.delete(a)
        for role_name in body.roles:
            session.add(
                GovernanceRoleAssignment(
                    subject_id=group_id,
                    subject_type="group",
                    role_name=role_name,
                )
            )
    session.commit()
    return {
        "group_id": group_id,
        "name": body.name or group_id,
        "description": body.description or "",
        "roles": body.roles or [a.role_name for a in existing_assignments],
        "members": [],
    }


@router.delete("/groups/{group_id}")
def delete_group(group_id: str, session: Session = Depends(get_session)):
    assignments = session.exec(
        select(GovernanceRoleAssignment).where(
            GovernanceRoleAssignment.subject_id == group_id
        )
    ).all()
    for a in assignments:
        session.delete(a)
    session.commit()
    return {"success": True}


@router.post("/groups/{group_id}/members")
def add_to_group(
    group_id: str, body: AddMemberRequest, session: Session = Depends(get_session)
):
    assignments = session.exec(
        select(GovernanceRoleAssignment).where(
            GovernanceRoleAssignment.subject_id == group_id
        )
    ).all()
    for a in assignments:
        session.add(
            GovernanceRoleAssignment(
                subject_id=body.agent_id,
                subject_type="agent",
                role_name=a.role_name,
            )
        )
    session.commit()
    return {"success": True}
