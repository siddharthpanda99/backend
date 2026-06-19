from typing import List
from fastapi import APIRouter, Depends
from sqlmodel import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.rbac.schemas import PermissionRead
from common_lib.modules.rbac.service import PermissionService
from app.modules.auth.dependencies import require_permission, require_tenant

router = APIRouter()


def get_permission_service(
    session: Session = Depends(get_session),
) -> PermissionService:
    return PermissionService(session)


@router.get(
    "/",
    response_model=List[PermissionRead],
    dependencies=[
        Depends(require_tenant),
        require_permission("permission.grant", "*", "permission"),
    ],
)
def read_permissions(
    skip: int = 0,
    limit: int = 100,
    service: PermissionService = Depends(get_permission_service),
):
    return service.list_permissions(skip=skip, limit=limit)
