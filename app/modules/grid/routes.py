from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.modules.grid.models import GridConfig
from app.modules.database.service.connection import get_session
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=GridConfig)
def save_grid_config(config: GridConfig, session: Session = Depends(get_session)):
    """Saves or updates a grid configuration."""
    existing = session.exec(select(GridConfig).where(GridConfig.name == config.name)).first()
    if existing:
        # Update existing
        data = config.model_dump(exclude_unset=True, exclude={"id", "created_at"})
        for key, value in data.items():
            setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    
    # Create new
    session.add(config)
    session.commit()
    session.refresh(config)
    return config

@router.get("/", response_model=List[GridConfig])
def list_grid_configs(
    session: Session = Depends(get_session),
    favorite_only: bool = Query(False)
):
    """Lists all saved grid configurations."""
    statement = select(GridConfig)
    if favorite_only:
        statement = statement.where(GridConfig.is_favorite == True)
    return session.exec(statement).all()

@router.delete("/{name}")
def delete_grid_config(name: str, session: Session = Depends(get_session)):
    """Deletes a grid configuration by name."""
    config = session.exec(select(GridConfig).where(GridConfig.name == name)).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    session.delete(config)
    session.commit()
    return {"status": "deleted"}

@router.patch("/{name}/favorite")
def toggle_favorite(name: str, is_favorite: bool, session: Session = Depends(get_session)):
    """Toggles the favorite status of a configuration."""
    config = session.exec(select(GridConfig).where(GridConfig.name == name)).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    config.is_favorite = is_favorite
    config.updated_at = datetime.utcnow()
    session.add(config)
    session.commit()
    session.refresh(config)
    return config
