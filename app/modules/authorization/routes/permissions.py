from typing import List
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.modules.database.service.connection import get_session
from common_lib.modules.rbac.schemas import PermissionRead
from common_lib.modules.rbac.service import PermissionService

router = APIRouter()


def get_permission_service(
    session: Session = Depends(get_session),
) -> PermissionService:
    return PermissionService(session)


@router.get("/", response_model=List[PermissionRead])
def read_permissions(
    skip: int = 0,
    limit: int = 100,
    service: PermissionService = Depends(get_permission_service),
):
    return service.list_permissions(skip=skip, limit=limit)
