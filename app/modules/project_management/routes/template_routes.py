"""
PM Template Routes — Thin API layer for project templates.

Registered at: /api/v1/jira/projects/templates
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
from common_lib.modules.project_management.projects.service import ProjectService
from common_lib.modules.project_management.schemas import ProjectRead

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=List[ProjectRead])
def list_templates(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("template.read", "*", "template"),
):
    """List all project templates (projects with status='template')."""
    svc = ProjectService(session)
    return svc.list_projects(limit=limit, offset=offset, template_only=True)


@router.get("/{template_id}", response_model=ProjectRead)
def get_template(
    template_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("template.read", "*", "template"),
):
    """Get a project template by ID."""
    svc = ProjectService(session)
    template = svc.get_project(template_id)
    if not template or template.status != "template":
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.post("/{project_id}/save-as-template", response_model=ProjectRead, status_code=201)
def save_as_template(
    project_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("template.create", "*", "template"),
):
    """Save an existing project as a reusable template."""
    svc = ProjectService(session)
    template = svc.save_project_as_template(project_id)
    if not template:
        raise HTTPException(status_code=404, detail="Project not found")
    return template


@router.post("/{template_id}/create-project", response_model=ProjectRead, status_code=201)
def create_from_template(
    template_id: str,
    name: str = Query(..., description="Name for the new project"),
    identifier: str = Query(..., description="Identifier for the new project (e.g. PROJ)"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("template.create", "*", "template"),
):
    """Create a new project from a template."""
    svc = ProjectService(session)
    project = svc.create_project_from_template(
        template_id=template_id,
        new_name=name,
        new_identifier=identifier,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Template not found or invalid")
    return project


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("template.delete", "*", "template"),
):
    """Delete a project template."""
    svc = ProjectService(session)
    if not svc.delete_project(template_id):
        raise HTTPException(status_code=404, detail="Template not found")
