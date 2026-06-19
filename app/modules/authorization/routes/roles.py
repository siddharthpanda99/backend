from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.rbac.schemas import RoleRead, RoleCreate, RoleUpdate
from common_lib.modules.rbac.service import RoleService
from common_lib.modules.auth.authorization import (
    PlatformIdentity,
    log_crud_mutation,
    check_hitl_before_destructive,
    sync_role_to_authz,
    remove_role_from_authz,
)
from app.modules.auth.dependencies import require_permission, require_tenant

router = APIRouter()


def get_role_service(session: Session = Depends(get_session)) -> RoleService:
    return RoleService(session)


@router.get(
    "/",
    response_model=List[RoleRead],
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def read_roles(
    skip: int = 0, limit: int = 100, service: RoleService = Depends(get_role_service)
):
    return service.list_roles(skip=skip, limit=limit)


@router.get(
    "/{role_id}",
    response_model=RoleRead,
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def read_role(role_id: int, service: RoleService = Depends(get_role_service)):
    role = service.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.post(
    "/",
    response_model=RoleRead,
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def create_role(
    request: Request,
    role_in: RoleCreate,
    service: RoleService = Depends(get_role_service),
):
    try:
        if service.get_role_by_name(role_in.name):
            raise HTTPException(status_code=400, detail="Role already exists")
        result = service.create_role(role_in)
        ident: PlatformIdentity = request.state.identity
        sync_role_to_authz(
            name=result.name,
            tenant_id=ident.tenant_id,
            created_by=ident.subject_id,
        )
        log_crud_mutation(
            subject_id=ident.subject_id,
            subject_type=ident.subject_type,
            action="role.create",
            resource_id=str(result.id),
            resource_type="role",
            tenant_id=ident.tenant_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/{role_id}",
    response_model=RoleRead,
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def update_role(
    request: Request,
    role_id: int,
    role_in: RoleUpdate,
    service: RoleService = Depends(get_role_service),
):
    role = service.update_role(role_id, role_in)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    ident: PlatformIdentity = request.state.identity
    log_crud_mutation(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="role.update",
        resource_id=str(role_id),
        resource_type="role",
        tenant_id=ident.tenant_id,
    )
    return role


@router.delete(
    "/{role_id}",
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def delete_role(
    request: Request,
    role_id: int,
    service: RoleService = Depends(get_role_service),
):
    ident: PlatformIdentity = request.state.identity
    role = service.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    hitl = check_hitl_before_destructive(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="role.delete",
        resource_id=str(role_id),
        resource_type="role",
        tenant_id=ident.tenant_id,
    )
    if hitl:
        raise HTTPException(status_code=202, detail=hitl)
    remove_role_from_authz(name=role.name, tenant_id=ident.tenant_id)
    if not service.delete_role(role_id):
        raise HTTPException(status_code=404, detail="Role not found")
    log_crud_mutation(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="role.delete",
        resource_id=str(role_id),
        resource_type="role",
        tenant_id=ident.tenant_id,
    )
    return {"ok": True}
