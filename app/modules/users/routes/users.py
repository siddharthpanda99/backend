from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.auth.users.schemas import UserRead, UserCreate, UserUpdate
from common_lib.modules.auth.users.service import UserService
from common_lib.modules.rbac.user_role_service import UserRoleService
from common_lib.modules.rbac.schemas import UserRoleGrant, UserRoleRead
from common_lib.modules.auth.authorization import PlatformIdentity, log_crud_mutation
from app.modules.auth.dependencies import require_permission, require_tenant

router = APIRouter()


def get_user_service(session: Session = Depends(get_session)) -> UserService:
    return UserService(session)


def get_user_role_service(session: Session = Depends(get_session)) -> UserRoleService:
    return UserRoleService(session)


@router.get(
    "/",
    response_model=List[UserRead],
    dependencies=[
        Depends(require_tenant),
        require_permission("user.read", "*", "user"),
    ],
)
def read_users(
    skip: int = 0,
    limit: int = 100,
    q: Optional[str] = Query(None, description="Search by username or email"),
    is_active: Optional[bool] = Query(None),
    tenant_id: Optional[str] = Query(None),
    service: UserService = Depends(get_user_service),
):
    return service.list_users(skip=skip, limit=limit)


@router.get(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[
        Depends(require_tenant),
        require_permission("user.read", "*", "user"),
    ],
)
def read_user(user_id: int, service: UserService = Depends(get_user_service)):
    user = service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post(
    "/",
    response_model=UserRead,
    dependencies=[
        Depends(require_tenant),
        require_permission("user.admin", "*", "user"),
    ],
)
def create_user(
    request: Request,
    user_in: UserCreate,
    service: UserService = Depends(get_user_service),
):
    if service.get_user_by_email(user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    result = service.create_user(user_in)
    ident: PlatformIdentity = request.state.identity
    log_crud_mutation(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="user.create",
        resource_id=str(result.id),
        resource_type="user",
        tenant_id=ident.tenant_id,
    )
    return result


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[
        Depends(require_tenant),
        require_permission("user.admin", "*", "user"),
    ],
)
def update_user(
    request: Request,
    user_id: int,
    user_in: UserUpdate,
    service: UserService = Depends(get_user_service),
):
    user = service.update_user(user_id, user_in)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    ident: PlatformIdentity = request.state.identity
    log_crud_mutation(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="user.update",
        resource_id=str(user_id),
        resource_type="user",
        tenant_id=ident.tenant_id,
    )
    return user


@router.delete(
    "/{user_id}",
    dependencies=[
        Depends(require_tenant),
        require_permission("user.admin", "*", "user"),
    ],
)
def delete_user(
    request: Request,
    user_id: int,
    service: UserService = Depends(get_user_service),
):
    if not service.delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    ident: PlatformIdentity = request.state.identity
    log_crud_mutation(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="user.delete",
        resource_id=str(user_id),
        resource_type="user",
        tenant_id=ident.tenant_id,
    )
    return {"ok": True}


# --- User Role Management ---


@router.get(
    "/{user_id}/roles",
    response_model=List[UserRoleRead],
    dependencies=[
        Depends(require_tenant),
        require_permission("user.read", "*", "user"),
    ],
)
def list_user_roles(
    user_id: int,
    include_inactive: bool = Query(False),
    svc: UserRoleService = Depends(get_user_role_service),
):
    return svc.list_user_roles(user_id, include_inactive=include_inactive)


@router.post(
    "/{user_id}/roles",
    response_model=UserRoleRead,
    dependencies=[
        Depends(require_tenant),
        require_permission("user.admin", "*", "user"),
    ],
)
def grant_user_role(
    request: Request,
    user_id: int,
    grant: UserRoleGrant,
    svc: UserRoleService = Depends(get_user_role_service),
):
    ident: PlatformIdentity = request.state.identity
    result = svc.grant(
        user_id=user_id,
        role_id=grant.role_id,
        granted_by=int(ident.subject_id) if ident.subject_id.isdigit() else None,
        org_id=grant.org_id,
        team_id=grant.team_id,
        expires_at=grant.expires_at,
    )
    log_crud_mutation(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="user.role.grant",
        resource_id=f"{user_id}:{grant.role_id}",
        resource_type="user_role",
        tenant_id=ident.tenant_id,
    )
    role = svc.session.get(
        __import__("common_lib.modules.rbac.models", fromlist=["Role"]).Role,
        grant.role_id,
    )
    return UserRoleRead(
        user_id=result.user_id,
        role_id=result.role_id,
        role_name=role.name if role else "",
        granted_by=result.granted_by,
        granted_at=result.granted_at,
        expires_at=result.expires_at,
        is_active=result.is_active,
        org_id=result.org_id,
        team_id=result.team_id,
    )


@router.delete(
    "/{user_id}/roles/{role_id}",
    dependencies=[
        Depends(require_tenant),
        require_permission("user.admin", "*", "user"),
    ],
)
def revoke_user_role(
    request: Request,
    user_id: int,
    role_id: int,
    reason: Optional[str] = Query(None),
    svc: UserRoleService = Depends(get_user_role_service),
):
    ident: PlatformIdentity = request.state.identity
    if not svc.revoke(user_id, role_id, reason=reason):
        raise HTTPException(status_code=404, detail="Role assignment not found")
    log_crud_mutation(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="user.role.revoke",
        resource_id=f"{user_id}:{role_id}",
        resource_type="user_role",
        tenant_id=ident.tenant_id,
    )
    return {"ok": True}
