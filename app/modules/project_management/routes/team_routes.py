"""
PM Team Routes — Thin API layer for Team CRUD.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission

def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)
from common_lib.modules.project_management.organization.service import TeamService
from common_lib.modules.project_management.schemas import (
    TeamCreate, TeamUpdate, TeamRead,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=List[TeamRead])
def list_teams(
    workspace_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("team.read", "*", "team"),
):
    svc = TeamService(session)
    return svc.list_teams(workspace_id=workspace_id, limit=limit, offset=offset)


@router.post("/", response_model=TeamRead, status_code=201)
def create_team(
    data: TeamCreate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("team.create", "*", "team"),
):
    svc = TeamService(session)
    try:
        return svc.create_team(data)
    except Exception as e:
        logger.exception("Failed to create team")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{team_id}", response_model=TeamRead)
def get_team(
    team_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("team.read", "*", "team"),
):
    svc = TeamService(session)
    team = svc.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.patch("/{team_id}", response_model=TeamRead)
def update_team(
    team_id: str,
    data: TeamUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("team.update", "*", "team"),
):
    svc = TeamService(session)
    team = svc.update_team(team_id, data)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.delete("/{team_id}", status_code=204)
def delete_team(
    team_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("team.delete", "*", "team"),
):
    svc = TeamService(session)
    if not svc.delete_team(team_id):
        raise HTTPException(status_code=404, detail="Team not found")
