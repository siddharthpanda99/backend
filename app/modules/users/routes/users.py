from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.users.schemas import UserRead, UserCreate, UserUpdate
from common_lib.modules.users.service import UserService

router = APIRouter()


def get_user_service(session: Session = Depends(get_session)) -> UserService:
    return UserService(session)


@router.get("/", response_model=List[UserRead])
def read_users(
    skip: int = 0, limit: int = 100, service: UserService = Depends(get_user_service)
):
    return service.list_users(skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserRead)
def read_user(user_id: int, service: UserService = Depends(get_user_service)):
    user = service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/", response_model=UserRead)
def create_user(user_in: UserCreate, service: UserService = Depends(get_user_service)):
    if service.get_user_by_email(user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    return service.create_user(user_in)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int, user_in: UserUpdate, service: UserService = Depends(get_user_service)
):
    user = service.update_user(user_id, user_in)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}")
def delete_user(user_id: int, service: UserService = Depends(get_user_service)):
    if not service.delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}
