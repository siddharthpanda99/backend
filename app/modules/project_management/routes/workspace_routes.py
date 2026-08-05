"""
PM Workspace Routes — Thin API layer for Workspace CRUD.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)
from common_lib.modules.project_management.organization.service import WorkspaceService
from common_lib.modules.project_management.schemas import (
    WorkspaceCreate, WorkspaceUpdate, WorkspaceRead,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=List[WorkspaceRead])
def list_workspaces(
    org_id: str = Query(None, description="Organization ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(_get_session),
):
    svc = WorkspaceService(session)
    return svc.list_workspaces(org_id, limit=limit, offset=offset)


@router.post("/", response_model=WorkspaceRead, status_code=201)
def create_workspace(
    data: WorkspaceCreate,
    session: Session = Depends(_get_session),
):
    svc = WorkspaceService(session)
    try:
        return svc.create_workspace(data.organization_id, data)
    except Exception as e:
        logger.exception("Failed to create workspace")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ws_id}", response_model=WorkspaceRead)
def get_workspace(
    ws_id: str,
    session: Session = Depends(_get_session),
):
    svc = WorkspaceService(session)
    ws = svc.get_workspace(ws_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.patch("/{ws_id}", response_model=WorkspaceRead)
def update_workspace(
    ws_id: str,
    data: WorkspaceUpdate,
    session: Session = Depends(_get_session),
):
    svc = WorkspaceService(session)
    ws = svc.update_workspace(ws_id, data)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.delete("/{ws_id}", status_code=204)
def delete_workspace(
    ws_id: str,
    session: Session = Depends(_get_session),
):
    svc = WorkspaceService(session)
    if not svc.delete_workspace(ws_id):
        raise HTTPException(status_code=404, detail="Workspace not found")
