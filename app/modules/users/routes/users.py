from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.users.schemas import UserRead, UserCreate, UserUpdate
from common_lib.modules.users.service import UserService
from common_lib.modules.auth.authorization import PlatformIdentity, log_crud_mutation
from app.modules.auth.dependencies import require_permission, require_tenant

router = APIRouter()


def get_user_service(session: Session = Depends(get_session)) -> UserService:
    return UserService(session)


@router.get(
    "/",
    response_model=List[UserRead],
    dependencies=[
        Depends(require_tenant),
        require_permission("user.read", "*", "user"),
    ],
)
def read_users(
    skip: int = 0, limit: int = 100, service: UserService = Depends(get_user_service)
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
