"""Theme routes — CRUD and preset management for site themes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.site_builder.services.theme_service import theme_service

router = APIRouter()


class ThemeCreateRequest(BaseModel):
    name: str
    tokens_json: dict = {}
    presets_json: dict = {}


class ThemeUpdateRequest(BaseModel):
    name: str | None = None
    tokens_json: dict | None = None
    presets_json: dict | None = None


class ThemeResponse(BaseModel):
    success: bool
    data: dict
    message: str


class ThemeListResponse(BaseModel):
    success: bool
    data: list
    message: str


class SuccessResponse(BaseModel):
    success: bool
    data: dict
    message: str


def _theme_to_dict(t) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "tokens_json": t.tokens_json,
        "presets_json": t.presets_json,
        "is_default": t.is_default,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.post("/themes", response_model=ThemeResponse)
def create_theme(req: ThemeCreateRequest, session: Session = Depends(get_db_session)):
    theme = theme_service.create(
        session,
        name=req.name,
        tokens_json=req.tokens_json,
        presets_json=req.presets_json,
    )
    return ThemeResponse(
        success=True, data=_theme_to_dict(theme), message="Theme created"
    )


@router.get("/themes", response_model=ThemeListResponse)
def list_themes(session: Session = Depends(get_db_session)):
    themes = theme_service.list(session)
    return ThemeListResponse(
        success=True,
        data=[_theme_to_dict(t) for t in themes],
        message=f"Found {len(themes)} themes",
    )


@router.get("/themes/{theme_id}", response_model=ThemeResponse)
def get_theme(theme_id: str, session: Session = Depends(get_db_session)):
    theme = theme_service.get(session, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    return ThemeResponse(
        success=True, data=_theme_to_dict(theme), message="Theme retrieved"
    )


@router.put("/themes/{theme_id}", response_model=ThemeResponse)
def update_theme(
    theme_id: str, req: ThemeUpdateRequest, session: Session = Depends(get_db_session)
):
    kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
    theme = theme_service.update(session, theme_id, **kwargs)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    return ThemeResponse(
        success=True, data=_theme_to_dict(theme), message="Theme updated"
    )


@router.delete("/themes/{theme_id}", response_model=SuccessResponse)
def delete_theme(theme_id: str, session: Session = Depends(get_db_session)):
    deleted = theme_service.delete(session, theme_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Theme not found")
    return SuccessResponse(success=True, data={}, message="Theme deleted")


@router.post("/themes/{theme_id}/presets/{preset_name}", response_model=ThemeResponse)
def apply_preset(
    theme_id: str, preset_name: str, session: Session = Depends(get_db_session)
):
    theme = theme_service.apply_preset(session, theme_id, preset_name)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme or preset not found")
    return ThemeResponse(
        success=True,
        data=_theme_to_dict(theme),
        message=f"Preset '{preset_name}' applied",
    )
