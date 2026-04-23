from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.modules.database.service.connection import get_session
from common_lib.modules.rbac.schemas import RoleRead, RoleCreate, RoleUpdate
from common_lib.modules.rbac.service import RoleService

router = APIRouter()


def get_role_service(session: Session = Depends(get_session)) -> RoleService:
    return RoleService(session)


@router.get("/", response_model=List[RoleRead])
def read_roles(
    skip: int = 0, limit: int = 100, service: RoleService = Depends(get_role_service)
):
    return service.list_roles(skip=skip, limit=limit)


@router.get("/{role_id}", response_model=RoleRead)
def read_role(role_id: int, service: RoleService = Depends(get_role_service)):
    role = service.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.post("/", response_model=RoleRead)
def create_role(role_in: RoleCreate, service: RoleService = Depends(get_role_service)):
    try:
        if service.get_role_by_name(role_in.name):
            raise HTTPException(status_code=400, detail="Role already exists")
        return service.create_role(role_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{role_id}", response_model=RoleRead)
def update_role(
    role_id: int, role_in: RoleUpdate, service: RoleService = Depends(get_role_service)
):
    role = service.update_role(role_id, role_in)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.delete("/{role_id}")
def delete_role(role_id: int, service: RoleService = Depends(get_role_service)):
    if not service.delete_role(role_id):
        raise HTTPException(status_code=404, detail="Role not found")
    return {"ok": True}
