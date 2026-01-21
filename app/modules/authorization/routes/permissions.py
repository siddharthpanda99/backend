from typing import List
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.modules.database.service.connection import get_session
from app.modules.authorization.schemas.permission import PermissionRead
from app.modules.authorization.service.role_service import PermissionService

router = APIRouter()

@router.get("/", response_model=List[PermissionRead])
def read_permissions(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session)
):
    service = PermissionService(session)
    return service.list_permissions(skip=skip, limit=limit)
