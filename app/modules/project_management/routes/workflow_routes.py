"""
PM Workflow Routes — Thin API layer.

Registered at: /api/v1/jira/workflows/
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


from common_lib.modules.project_management.workflows.service import WorkflowService
from common_lib.modules.project_management.schemas import (
    WorkflowCreate,
    WorkflowRead,
    WorkflowStatusCreate,
    WorkflowStatusRead,
    WorkflowTransitionCreate,
    WorkflowTransitionRead,
    AutomationTemplateCreate,
    AutomationTemplateUpdate,
    AutomationTemplateInstantiate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ===========================================================================
# Workflows
# ===========================================================================


@router.get("/", response_model=List[WorkflowRead])
def list_workflows(
    project_id: str = Query(...),
    _perm: None = require_permission("workflow.read", "*", "workflow"),
    session: Session = Depends(_get_session),
):
    """List workflows for a project."""
    svc = WorkflowService(session)
    from sqlmodel import select
    from common_lib.modules.project_management.workflows.models import Workflow

    return list(
        session.exec(select(Workflow).where(Workflow.project_id == project_id)).all()
    )


@router.post("/", response_model=WorkflowRead, status_code=201)
def create_workflow(
    data: WorkflowCreate,
    _perm: None = require_permission("workflow.create", "*", "workflow"),
    session: Session = Depends(_get_session),
):
    """Create a new workflow."""
    svc = WorkflowService(session)
    return svc.create_workflow(data.model_dump())


@router.get("/{workflow_id}", response_model=WorkflowRead)
def get_workflow(
    workflow_id: str,
    _perm: None = require_permission("workflow.read", "*", "workflow"),
    session: Session = Depends(_get_session),
):
    """Get workflow by ID."""
    svc = WorkflowService(session)
    wf = svc.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


# ===========================================================================
# Workflow Statuses
# ===========================================================================


@router.get("/{workflow_id}/statuses", response_model=List[WorkflowStatusRead])
def list_statuses(
    workflow_id: str,
    _perm: None = require_permission("workflow.read", "*", "workflow"),
    session: Session = Depends(_get_session),
):
    """List statuses in a workflow."""
    svc = WorkflowService(session)
    return svc.list_statuses(workflow_id)


@router.post(
    "/{workflow_id}/statuses", response_model=WorkflowStatusRead, status_code=201
)
def create_status(
    workflow_id: str,
    data: WorkflowStatusCreate,
    _perm: None = require_permission("workflow.create", "*", "workflow"),
    session: Session = Depends(_get_session),
):
    """Add a status to a workflow."""
    svc = WorkflowService(session)
    return svc.create_status({**data.model_dump(), "workflow_id": workflow_id})


# ===========================================================================
# Workflow Transitions
# ===========================================================================


@router.get("/{workflow_id}/transitions", response_model=List[WorkflowTransitionRead])
def list_transitions(
    workflow_id: str,
    _perm: None = require_permission("workflow.read", "*", "workflow"),
    session: Session = Depends(_get_session),
):
    """List transitions in a workflow."""
    svc = WorkflowService(session)
    return svc.list_transitions(workflow_id)


@router.post(
    "/{workflow_id}/transitions", response_model=WorkflowTransitionRead, status_code=201
)
def create_transition(
    workflow_id: str,
    data: WorkflowTransitionCreate,
    _perm: None = require_permission("workflow.create", "*", "workflow"),
    session: Session = Depends(_get_session),
):
    """Add a transition to a workflow."""
    svc = WorkflowService(session)
    return svc.create_transition({**data.model_dump(), "workflow_id": workflow_id})


# ===========================================================================
# Automation Templates — Domain 17.06
# ===========================================================================


@router.get("/automation-templates/categories")
def list_automation_template_categories(
    _perm: None = require_permission("automation.read", "*", "automation"),
    session: Session = Depends(_get_session),
):
    """List all available automation template categories."""
    svc = WorkflowService(session)
    return svc.list_automation_template_categories()


@router.post("/automation-templates", status_code=201)
def create_automation_template(
    data: AutomationTemplateCreate,
    _perm: None = require_permission("automation.create", "*", "automation"),
    session: Session = Depends(_get_session),
):
    """Create a new automation template."""
    svc = WorkflowService(session)
    return svc.create_automation_template(
        name=data.name,
        description=data.description,
        category=data.category,
        trigger_type=data.trigger_type,
        trigger_config=data.trigger_config,
        condition_config=data.condition_config,
        actions=data.actions,
        parameters_schema=data.parameters_schema,
        project_id=data.project_id,
        is_global=data.is_global,
        tags=data.tags,
    )


@router.get("/automation-templates")
def list_automation_templates(
    project_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    is_global: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("automation.read", "*", "automation"),
    session: Session = Depends(_get_session),
):
    """List automation templates with optional filters."""
    svc = WorkflowService(session)
    templates = svc.list_automation_templates(
        project_id=project_id,
        category=category,
        is_global=is_global,
        limit=limit,
        offset=offset,
    )
    return {"items": [t.model_dump() for t in templates], "total": len(templates)}


@router.get("/automation-templates/{template_id}")
def get_automation_template(
    template_id: str,
    _perm: None = require_permission("automation.read", "*", "automation"),
    session: Session = Depends(_get_session),
):
    """Get an automation template by ID."""
    svc = WorkflowService(session)
    template = svc.get_automation_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Automation template not found")
    return template


@router.patch("/automation-templates/{template_id}")
def update_automation_template(
    template_id: str,
    data: AutomationTemplateUpdate,
    _perm: None = require_permission("automation.update", "*", "automation"),
    session: Session = Depends(_get_session),
):
    """Update an automation template."""
    svc = WorkflowService(session)
    template = svc.update_automation_template(
        template_id, data.model_dump(exclude_unset=True)
    )
    if not template:
        raise HTTPException(status_code=404, detail="Automation template not found")
    return template


@router.delete("/automation-templates/{template_id}", status_code=204)
def delete_automation_template(
    template_id: str,
    _perm: None = require_permission("automation.delete", "*", "automation"),
    session: Session = Depends(_get_session),
):
    """Delete an automation template."""
    svc = WorkflowService(session)
    if not svc.delete_automation_template(template_id):
        raise HTTPException(status_code=404, detail="Automation template not found")


@router.post("/automation-templates/{template_id}/instantiate")
def instantiate_automation_template(
    template_id: str,
    data: AutomationTemplateInstantiate,
    _perm: None = require_permission("automation.create", "*", "automation"),
    session: Session = Depends(_get_session),
):
    """Instantiate an automation template into a project.

    Creates an active automation configuration in the target project
    by filling in template parameters and generating concrete
    trigger/condition/action configuration.
    """
    svc = WorkflowService(session)
    try:
        config = svc.instantiate_automation_template(
            template_id=template_id,
            project_id=data.project_id,
            parameter_values=data.parameter_values,
            name_override=data.name_override,
        )
        return config
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
