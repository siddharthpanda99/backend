from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.grid.models import GridConfig
from common_lib.modules.grid.service import grid_service, NotFoundError

router = APIRouter()


@router.post("/", response_model=GridConfig)
def save_grid_config(config: GridConfig, session: Session = Depends(get_session)):
    return grid_service.save_grid_config(session, config)


@router.get("/", response_model=List[GridConfig])
def list_grid_configs(
    session: Session = Depends(get_session),
    favorite_only: bool = Query(False),
):
    return grid_service.list_grid_configs(session, favorite_only)


@router.delete("/{name}")
def delete_grid_config(name: str, session: Session = Depends(get_session)):
    grid_service.delete_grid_config(session, name)
    return {"status": "deleted"}


@router.patch("/{name}/favorite")
def toggle_favorite(
    name: str, is_favorite: bool, session: Session = Depends(get_session)
):
    try:
        return grid_service.toggle_favorite(session, name, is_favorite)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Config not found")


__all__ = ["router"]
