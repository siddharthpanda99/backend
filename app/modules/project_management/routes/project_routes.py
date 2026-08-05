"""
PM Project Routes — Thin API layer.

Registered at: /api/v1/jira/projects/
"""
from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)
from common_lib.modules.project_management.projects.service import ProjectService
from common_lib.modules.project_management.schemas import (
    ProjectCreate, ProjectUpdate, ProjectRead, ProjectStats,
    IssueTypeCreate, IssueTypeUpdate, IssueTypeRead,
    ProjectBlueprintCreate, ProjectBlueprintUpdate, BlueprintProvisionRequest,
    BlueprintBulkProvisionRequest, BlueprintPropagateRequest,
)
from app.modules.project_management.field_security_deps import (
    filter_single_response,
    filter_list_response,
    check_field_editable,
    strip_field_security_metadata,
)
from app.modules.auth.dependencies import require_permission

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=List[ProjectRead])
def list_projects(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("project.read", "*", "project"),
):
    """List all projects."""
    svc = ProjectService(session)
    projects = svc.list_projects(limit=limit, offset=offset, status=status)
    items = [ProjectRead.model_validate(p).model_dump() for p in projects]
    items = filter_list_response(request, session, "project", items)
    return items


@router.post("/", response_model=ProjectRead, status_code=201)
def create_project(
    data: ProjectCreate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("project.create", "*", "project"),
):
    """Create a new project."""
    svc = ProjectService(session)
    try:
        return svc.create_project(data)
    except Exception as e:
        logger.exception("Failed to create project")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    request: Request,
    project_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("project.read", "*", "project"),
):
    """Get project by ID."""
    svc = ProjectService(session)
    project = svc.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    data = ProjectRead.model_validate(project).model_dump()
    data = filter_single_response(request, session, "project", data, project_id=project_id)
    return strip_field_security_metadata(data)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    request: Request,
    project_id: str,
    data: ProjectUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("project.update", "*", "project"),
):
    """Update a project."""
    svc = ProjectService(session)
    update_fields = data.model_dump(exclude_unset=True)
    for field_key in update_fields:
        if not check_field_editable(request, session, "project", field_key, project_id=project_id):
            raise HTTPException(status_code=403, detail=f"Field '{field_key}' is not editable for your role")
    project = svc.update_project(project_id, data)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("project.delete", "*", "project"),
):
    """Delete a project."""
    svc = ProjectService(session)
    if not svc.delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/{project_id}/issue-types", response_model=List[IssueTypeRead])
def list_issue_types(
    project_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("project.read", "*", "project"),
):
    """List all issue types for a project."""
    svc = ProjectService(session)
    return svc.list_issue_types(project_id)


@router.post("/{project_id}/issue-types", response_model=IssueTypeRead, status_code=201)
def create_issue_type(
    project_id: str,
    data: IssueTypeCreate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("project.update", "*", "project"),
):
    """Create a new issue type for a project."""
    svc = ProjectService(session)
    try:
        return svc.create_issue_type(project_id=project_id, **data.model_dump())
    except Exception as e:
        logger.exception("Failed to create issue type")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{project_id}/issue-types/{issue_type_id}", response_model=IssueTypeRead)
def update_issue_type(
    project_id: str,
    issue_type_id: str,
    data: IssueTypeUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("project.update", "*", "project"),
):
    """Update an existing issue type."""
    svc = ProjectService(session)
    it = svc.update_issue_type(issue_type_id=issue_type_id, **data.model_dump())
    if not it:
        raise HTTPException(status_code=404, detail="Issue type not found")
    return it


@router.get("/{project_id}/stats", response_model=ProjectStats)
def get_project_stats(
    project_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("project.read", "*", "project"),
):
    """Get project statistics."""
    svc = ProjectService(session)
    project = svc.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return svc.get_project_stats(project_id)


# ===========================================================================
# Blueprint Endpoints — Domain 22.02-22.05
# ===========================================================================


@router.post("/blueprints", status_code=201)
def create_blueprint(
    data: ProjectBlueprintCreate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("blueprint.create", "*", "blueprint"),
):
    """Create a new project blueprint."""
    svc = ProjectService(session)
    return svc.create_blueprint(data.model_dump())


@router.get("/blueprints")
def list_blueprints(
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("blueprint.read", "*", "blueprint"),
):
    """List project blueprints."""
    svc = ProjectService(session)
    blueprints = svc.list_blueprints(category=category, is_active=is_active, limit=limit, offset=offset)
    return {"items": [b.model_dump() for b in blueprints], "total": len(blueprints)}


@router.get("/blueprints/{blueprint_id}")
def get_blueprint(
    blueprint_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("blueprint.read", "*", "blueprint"),
):
    """Get a blueprint by ID."""
    svc = ProjectService(session)
    bp = svc.get_blueprint(blueprint_id)
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    return bp


@router.patch("/blueprints/{blueprint_id}")
def update_blueprint(
    blueprint_id: str,
    data: ProjectBlueprintUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("blueprint.update", "*", "blueprint"),
):
    """Update a blueprint."""
    svc = ProjectService(session)
    bp = svc.update_blueprint(blueprint_id, data)
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    return bp


@router.delete("/blueprints/{blueprint_id}", status_code=204)
def delete_blueprint(
    blueprint_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("blueprint.delete", "*", "blueprint"),
):
    """Delete a blueprint."""
    svc = ProjectService(session)
    if not svc.delete_blueprint(blueprint_id):
        raise HTTPException(status_code=404, detail="Blueprint not found")


@router.post("/blueprints/{blueprint_id}/provision", status_code=201)
def provision_blueprint(
    blueprint_id: str,
    data: BlueprintProvisionRequest,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("project.create", "*", "project"),
):
    """Provision a new project from a blueprint."""
    svc = ProjectService(session)
    try:
        project = svc.provision_blueprint(
            blueprint_id=blueprint_id,
            name=data.name,
            identifier=data.identifier,
            description=data.description,
            lead_id=data.lead_id,
            slug=data.slug,
            settings_overrides=data.settings_overrides,
        )
        return project
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/blueprints/{blueprint_id}/propagate")
def propagate_blueprint(
    blueprint_id: str,
    data: BlueprintPropagateRequest,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("blueprint.update", "*", "blueprint"),
):
    """Propagate blueprint changes to linked projects."""
    svc = ProjectService(session)
    try:
        return svc.propagate_blueprint_changes(
            blueprint_id=blueprint_id,
            project_ids=data.project_ids,
            fields=data.fields,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/blueprints/control-center")
def get_blueprint_control_center(
    session: Session = Depends(_get_session),
    _perm: None = require_permission("blueprint.read", "*", "blueprint"),
):
    """Get the blueprint control center overview."""
    svc = ProjectService(session)
    return svc.get_blueprint_control_center()


@router.post("/blueprints/{blueprint_id}/bulk-provision", status_code=201)
def bulk_provision_blueprint(
    blueprint_id: str,
    data: BlueprintBulkProvisionRequest,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("project.create", "*", "project"),
):
    """Bulk provision multiple projects from a blueprint."""
    svc = ProjectService(session)
    try:
        return svc.bulk_provision_blueprint(
            blueprint_id=blueprint_id,
            projects=[p.model_dump() for p in data.projects],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
