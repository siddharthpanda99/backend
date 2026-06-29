from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.rbac.schemas import (
    RoleRead,
    RoleCreate,
    RoleUpdate,
    PermissionRead,
    RoleInheritanceCreate,
    RoleInheritanceRead,
)
from common_lib.modules.rbac.service import RoleService, PermissionService
from common_lib.modules.rbac.authorization_engine import PermissionResolver
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


def get_permission_service(
    session: Session = Depends(get_session),
) -> PermissionService:
    return PermissionService(session)


def get_permission_resolver(
    session: Session = Depends(get_session),
) -> PermissionResolver:
    return PermissionResolver(session)


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


# --- Role Permission Management ---


@router.get(
    "/{role_id}/permissions",
    response_model=List[PermissionRead],
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def list_role_permissions(
    role_id: int,
    service: RoleService = Depends(get_role_service),
):
    role = service.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    from common_lib.modules.rbac.models import RolePermission, Permission
    from sqlalchemy import select

    perm_ids = [
        rp.permission_id
        for rp in service.session.exec(
            select(RolePermission).where(RolePermission.role_id == role_id)
        ).all()
    ]
    if not perm_ids:
        return []
    perms = service.session.exec(
        select(Permission).where(Permission.id.in_(perm_ids))
    ).all()
    return perms


@router.post(
    "/{role_id}/permissions",
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def add_role_permission(
    request: Request,
    role_id: int,
    permission_id: int = Query(...),
    service: RoleService = Depends(get_role_service),
):
    from common_lib.modules.rbac.models import RolePermission, Permission

    role = service.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    perm = service.session.get(Permission, permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    existing = service.session.exec(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
    ).first()
    if existing:
        return {"ok": True, "already_exists": True}
    service.session.add(RolePermission(role_id=role_id, permission_id=permission_id))
    service.session.commit()
    ident: PlatformIdentity = request.state.identity
    log_crud_mutation(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="role.permission.add",
        resource_id=f"{role_id}:{permission_id}",
        resource_type="role_permission",
        tenant_id=ident.tenant_id,
    )
    return {"ok": True}


@router.delete(
    "/{role_id}/permissions/{permission_id}",
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def remove_role_permission(
    request: Request,
    role_id: int,
    permission_id: int,
    service: RoleService = Depends(get_role_service),
):
    from common_lib.modules.rbac.models import RolePermission

    link = service.session.exec(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Permission not assigned to role")
    service.session.delete(link)
    service.session.commit()
    ident: PlatformIdentity = request.state.identity
    log_crud_mutation(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="role.permission.remove",
        resource_id=f"{role_id}:{permission_id}",
        resource_type="role_permission",
        tenant_id=ident.tenant_id,
    )
    return {"ok": True}


# --- Role Inheritance ---


@router.get(
    "/{role_id}/parents",
    response_model=List[RoleRead],
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def list_role_parents(
    role_id: int,
    service: RoleService = Depends(get_role_service),
):
    return service.get_parents(role_id)


@router.post(
    "/{role_id}/inherit",
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def add_role_parent(
    request: Request,
    role_id: int,
    body: RoleInheritanceCreate,
    service: RoleService = Depends(get_role_service),
):
    try:
        result = service.add_parent_role(
            child_role_id=role_id, parent_role_id=body.parent_role_id
        )
        if not result:
            return {"ok": True, "already_exists": True}
        ident: PlatformIdentity = request.state.identity
        log_crud_mutation(
            subject_id=ident.subject_id,
            subject_type=ident.subject_type,
            action="role.inherit.add",
            resource_id=f"{role_id}:{body.parent_role_id}",
            resource_type="role_inheritance",
            tenant_id=ident.tenant_id,
        )
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{role_id}/inherit/{parent_role_id}",
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def remove_role_parent(
    request: Request,
    role_id: int,
    parent_role_id: int,
    service: RoleService = Depends(get_role_service),
):
    if not service.remove_parent_role(
        child_role_id=role_id, parent_role_id=parent_role_id
    ):
        raise HTTPException(status_code=404, detail="Inheritance not found")
    ident: PlatformIdentity = request.state.identity
    log_crud_mutation(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="role.inherit.remove",
        resource_id=f"{role_id}:{parent_role_id}",
        resource_type="role_inheritance",
        tenant_id=ident.tenant_id,
    )
    return {"ok": True}


# --- Effective Permissions ---


@router.get(
    "/{role_id}/effective-permissions",
    response_model=List[PermissionRead],
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def get_effective_permissions(
    role_id: int,
    service: RoleService = Depends(get_role_service),
    resolver: PermissionResolver = Depends(get_permission_resolver),
):
    role = service.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    from sqlalchemy import select
    from common_lib.modules.rbac.models import RolePermission, Permission

    all_role_ids = resolver.get_effective_role_ids(role_id)
    perm_ids = [
        rp.permission_id
        for rp in service.session.exec(
            select(RolePermission).where(RolePermission.role_id.in_(all_role_ids))
        ).all()
    ]
    if not perm_ids:
        return []
    return list(
        service.session.exec(
            select(Permission).where(Permission.id.in_(perm_ids))
        ).all()
    )
