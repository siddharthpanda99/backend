from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.team.models import WorkspaceSetting
from common_lib.modules.team.service import workspace_service

router = APIRouter()


class RBACConfig(BaseModel):
    roles: List[Dict[str, Any]] = []
    navPermissions: Dict[str, List[str]] = {}
    apiPermissions: Dict[str, List[str]] = {}


@router.get("/{team_id}/rbac")
def get_rbac(team_id: int, session: Session = Depends(get_session)):
    settings = workspace_service.get_settings(session, team_id)
    if not settings:
        return RBACConfig().model_dump()
    try:
        parsed = __import__("json").loads(settings.settings_json)
        rbac = parsed.get("rbac", {})
        return RBACConfig(**rbac).model_dump()
    except (__import__("json").JSONDecodeError, TypeError):
        return RBACConfig().model_dump()


@router.put("/{team_id}/rbac")
def save_rbac(team_id: int, body: RBACConfig, session: Session = Depends(get_session)):
    settings = workspace_service.get_settings(session, team_id)
    if not settings:
        settings = WorkspaceSetting(team_id=team_id, settings_json="{}")
    try:
        parsed = __import__("json").loads(settings.settings_json)
    except (__import__("json").JSONDecodeError, TypeError):
        parsed = {}
    parsed["rbac"] = body.model_dump()
    settings.settings_json = __import__("json").dumps(parsed)
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return body.model_dump()


@router.get("/{team_id}/rbac/roles")
def get_rbac_roles(team_id: int, session: Session = Depends(get_session)):
    config = get_rbac(team_id, session)
    return config.get("roles", [])


@router.put("/{team_id}/rbac/roles")
def save_rbac_roles(
    team_id: int, body: List[Dict[str, Any]], session: Session = Depends(get_session)
):
    config = get_rbac(team_id, session)
    config["roles"] = body
    return save_rbac(team_id, RBACConfig(**config), session)


@router.get("/{team_id}/rbac/nav")
def get_rbac_nav(team_id: int, session: Session = Depends(get_session)):
    config = get_rbac(team_id, session)
    return config.get("navPermissions", {})


@router.put("/{team_id}/rbac/nav")
def save_rbac_nav(
    team_id: int, body: Dict[str, List[str]], session: Session = Depends(get_session)
):
    config = get_rbac(team_id, session)
    config["navPermissions"] = body
    return save_rbac(team_id, RBACConfig(**config), session)


@router.get("/{team_id}/rbac/api")
def get_rbac_api(team_id: int, session: Session = Depends(get_session)):
    config = get_rbac(team_id, session)
    return config.get("apiPermissions", {})


@router.put("/{team_id}/rbac/api")
def save_rbac_api(
    team_id: int, body: Dict[str, List[str]], session: Session = Depends(get_session)
):
    config = get_rbac(team_id, session)
    config["apiPermissions"] = body
    return save_rbac(team_id, RBACConfig(**config), session)
