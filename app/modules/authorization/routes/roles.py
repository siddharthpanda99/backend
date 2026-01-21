from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.modules.database.service.connection import get_session
from app.modules.authorization.schemas.role import RoleRead, RoleCreate, RoleUpdate
from app.modules.authorization.service.role_service import RoleService

router = APIRouter()

@router.get("/", response_model=List[RoleRead])
def read_roles(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session)
):
    service = RoleService(session)
    return service.list_roles(skip=skip, limit=limit)

@router.get("/{role_id}", response_model=RoleRead)
def read_role(
    role_id: int,
    session: Session = Depends(get_session)
):
    service = RoleService(session)
    role = service.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role

@router.post("/", response_model=RoleRead)
def create_role(
    role_in: RoleCreate,
    session: Session = Depends(get_session)
):
    service = RoleService(session)
    try:
        if service.get_role_by_name(role_in.name):
            raise HTTPException(status_code=400, detail="Role already exists")
        return service.create_role(role_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{role_id}", response_model=RoleRead)
def update_role(
    role_id: int,
    role_in: RoleUpdate,
    session: Session = Depends(get_session)
):
    service = RoleService(session)
    role = service.update_role(role_id, role_in)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role

@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    session: Session = Depends(get_session)
):
    service = RoleService(session)
    if not service.delete_role(role_id):
        raise HTTPException(status_code=404, detail="Role not found")
    return {"ok": True}
