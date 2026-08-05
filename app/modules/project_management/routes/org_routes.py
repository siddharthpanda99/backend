"""
PM Organization Routes — Thin API layer for Organization, Workspace, Team CRUD.
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
from common_lib.modules.project_management.organization.service import (
    OrganizationService,
    WorkspaceService,
    TeamService,
)
from common_lib.modules.project_management.schemas import (
    OrganizationCreate, OrganizationUpdate, OrganizationRead,
    OrganizationBrandingUpdate,
    WorkspaceCreate, WorkspaceUpdate, WorkspaceRead,
    TeamCreate, TeamUpdate, TeamRead,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ===========================================================================
# Organization CRUD
# ===========================================================================

@router.get("/", response_model=List[OrganizationRead])
def list_orgs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("organization.read", "*", "organization"),
):
    svc = OrganizationService(session)
    orgs = svc.list_organizations(limit=limit, offset=offset)
    return [OrganizationRead.model_validate(o) for o in orgs]


@router.post("/", response_model=OrganizationRead, status_code=201)
def create_org(
    data: OrganizationCreate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("organization.create", "*", "organization"),
):
    svc = OrganizationService(session)
    try:
        org = svc.create_organization(data)
        return OrganizationRead.model_validate(org)
    except Exception as e:
        logger.exception("Failed to create organization")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{org_id}", response_model=OrganizationRead)
def get_org(
    org_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("organization.read", "*", "organization"),
):
    svc = OrganizationService(session)
    org = svc.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationRead.model_validate(org)


@router.patch("/{org_id}", response_model=OrganizationRead)
def update_org(
    org_id: str,
    data: OrganizationUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("organization.update", "*", "organization"),
):
    svc = OrganizationService(session)
    org = svc.update_organization(org_id, data)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationRead.model_validate(org)


@router.delete("/{org_id}", status_code=204)
def delete_org(
    org_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("organization.delete", "*", "organization"),
):
    svc = OrganizationService(session)
    if not svc.delete_organization(org_id):
        raise HTTPException(status_code=404, detail="Organization not found")


@router.patch("/{org_id}/branding", response_model=OrganizationRead)
def update_org_branding(
    org_id: str,
    data: OrganizationBrandingUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("organization.update", "*", "organization"),
):
    """Update organization branding/profile settings."""
    svc = OrganizationService(session)
    org = svc.update_organization_branding(org_id, data)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationRead.model_validate(org)


# ===========================================================================
# Workspace CRUD (nested under organizations)
# ===========================================================================

@router.get("/{org_id}/workspaces", response_model=List[WorkspaceRead])
def list_workspaces(
):
    svc = WorkspaceService(session)
    ws_list = svc.list_workspaces(organization_id=org_id, limit=limit, offset=offset)
    return [WorkspaceRead.model_validate(w) for w in ws_list]


@router.post("/{org_id}/workspaces", response_model=WorkspaceRead, status_code=201)
def create_workspace(
):
    svc = WorkspaceService(session)
    data.organization_id = org_id
    ws = svc.create_workspace(data)
    return WorkspaceRead.model_validate(ws)


@router.get("/{org_id}/workspaces/{ws_id}", response_model=WorkspaceRead)
def get_workspace(
):
    svc = WorkspaceService(session)
    ws = svc.get_workspace(ws_id)
    if not ws or ws.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceRead.model_validate(ws)


@router.patch("/{org_id}/workspaces/{ws_id}", response_model=WorkspaceRead)
def update_workspace(
):
    svc = WorkspaceService(session)
    ws = svc.get_workspace(ws_id)
    if not ws or ws.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws = svc.update_workspace(ws_id, data)
    return WorkspaceRead.model_validate(ws)


@router.delete("/{org_id}/workspaces/{ws_id}", status_code=204)
def delete_workspace(
):
    svc = WorkspaceService(session)
    ws = svc.get_workspace(ws_id)
    if not ws or ws.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    svc.delete_workspace(ws_id)


# ===========================================================================
# Workspace Templates (01.10)
# ===========================================================================

@router.post("/{org_id}/workspaces/{ws_id}/save-template", status_code=201)
def save_workspace_template(
):
    """Save an existing workspace as a reusable template."""
    svc = WorkspaceService(session)
    ws = svc.get_workspace(ws_id)
    if not ws or ws.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    template = svc.save_workspace_template(ws_id)
    return template


@router.post("/{org_id}/workspaces/from-template", response_model=WorkspaceRead, status_code=201)
def create_workspace_from_template(
):
    """Create a new workspace from a template."""
    svc = WorkspaceService(session)
    ws = svc.create_workspace_from_template(org_id, template_id, name)
    if not ws:
        raise HTTPException(status_code=404, detail="Template not found or not available in this organization")
    return WorkspaceRead.model_validate(ws)


@router.get("/{org_id}/workspace-templates")
def list_workspace_templates(
):
    """List available workspace templates for an organization."""
    svc = WorkspaceService(session)
    templates = svc.list_workspace_templates(org_id)
    return {"templates": templates, "total": len(templates)}


# ===========================================================================
# Workspace Duplication (01.11)
# ===========================================================================

@router.post("/{org_id}/workspaces/{ws_id}/duplicate", response_model=WorkspaceRead, status_code=201)
def duplicate_workspace(
):
    """Duplicate an existing workspace with all its settings."""
    svc = WorkspaceService(session)
    ws = svc.duplicate_workspace(org_id, ws_id, name)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceRead.model_validate(ws)


# ===========================================================================
# Team CRUD (nested under organizations)
# ===========================================================================

@router.get("/{org_id}/teams", response_model=List[TeamRead])
def list_teams(
):
    svc = TeamService(session)
    team_list = svc.list_teams(workspace_id=workspace_id, limit=limit, offset=offset)
    return [TeamRead.model_validate(t) for t in team_list]


@router.post("/{org_id}/teams", response_model=TeamRead, status_code=201)
def create_team(
):
    svc = TeamService(session)
    team = svc.create_team(data)
    return TeamRead.model_validate(team)


@router.get("/{org_id}/teams/{team_id}", response_model=TeamRead)
def get_team(
):
    svc = TeamService(session)
    team = svc.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return TeamRead.model_validate(team)


@router.patch("/{org_id}/teams/{team_id}", response_model=TeamRead)
def update_team(
):
    svc = TeamService(session)
    team = svc.update_team(team_id, data)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return TeamRead.model_validate(team)


@router.delete("/{org_id}/teams/{team_id}", status_code=204)
def delete_team(
):
    svc = TeamService(session)
    if not svc.delete_team(team_id):
        raise HTTPException(status_code=404, detail="Team not found")


# ===========================================================================
# Team Workload Views (01.12)
# ===========================================================================

@router.get("/{org_id}/teams/{team_id}/workload")
def get_team_workload(
):
    """Get workload view for a team showing issues per member."""
    svc = TeamService(session)
    return svc.get_team_workload(team_id, sprint_id=sprint_id)
