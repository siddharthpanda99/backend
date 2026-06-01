from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.ext_apps.models import ExtAppView
from ..schemas import ExtAppViewCreate, ExtAppViewUpdate, ExtAppViewResponse

router = APIRouter(prefix="/views", tags=["Ext-Apps"])

@router.post("/", response_model=ExtAppViewResponse)
async def create_view(
    view_data: ExtAppViewCreate,
    db: Session = Depends(get_session)
):
    existing = db.execute(select(ExtAppView).where(ExtAppView.name == view_data.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="View with this name already exists")
        
    new_view = ExtAppView(**view_data.model_dump())
    db.add(new_view)
    db.commit()
    db.refresh(new_view)
    return new_view

@router.get("/", response_model=List[ExtAppViewResponse])
async def list_views(
    db: Session = Depends(get_session)
):
    result = db.execute(select(ExtAppView))
    return result.scalars().all()

@router.get("/{view_id}", response_model=ExtAppViewResponse)
async def get_view(
    view_id: str,
    db: Session = Depends(get_session)
):
    view = db.execute(select(ExtAppView).where(ExtAppView.id == view_id)).scalar_one_or_none()
    if not view:
        raise HTTPException(status_code=404, detail="View not found")
    return view

@router.put("/{view_id}", response_model=ExtAppViewResponse)
async def update_view(
    view_id: str,
    update_data: ExtAppViewUpdate,
    db: Session = Depends(get_session)
):
    view = db.execute(select(ExtAppView).where(ExtAppView.id == view_id)).scalar_one_or_none()
    if not view:
        raise HTTPException(status_code=404, detail="View not found")
        
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(view, key, value)
        
    db.commit()
    db.refresh(view)
    return view
