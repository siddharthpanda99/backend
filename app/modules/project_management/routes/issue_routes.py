"""
PM Issue Routes — Thin API layer.

Registered at: /api/v1/jira/issues/
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


from common_lib.modules.project_management.issues.service import IssueService
from common_lib.modules.project_management.schemas import (
    IssueCreate,
    IssueUpdate,
    IssueRead,
    IssueQuery,
    IssueTransition,
    IssueBulkUpdate,
    IssueLinkCreate,
    IssueLinkRead,
    CommentCreate,
    CommentRead,
    ActivityRead,
    PaginatedResponse,
    TaskRecurrenceCreate,
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


@router.get("/", response_model=PaginatedResponse)
def list_issues(
    request: Request,
    project_id: Optional[str] = Query(None),
    sprint_id: Optional[str] = Query(None),
    epic_id: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    status_id: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    issue_type_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("issue.read", "*", "issue"),
):
    """List issues with filters (JQL-like)."""
    svc = IssueService(session)
    query = IssueQuery(
        project_id=project_id,
        sprint_id=sprint_id,
        epic_id=epic_id,
        assignee_id=assignee_id,
        status_id=status_id,
        priority=priority,
        issue_type_id=issue_type_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )
    result = svc.list_issues(query)
    items = [i.model_dump() for i in result["items"]]
    items = filter_list_response(
        request, session, "issue", items, project_id=project_id
    )
    return PaginatedResponse(
        items=[IssueRead.model_validate(i) for i in items],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
        has_more=result["has_more"],
    )


@router.post("/", response_model=IssueRead, status_code=201)
def create_issue(
    data: IssueCreate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("issue.create", "*", "issue"),
):
    """Create a new issue."""
    svc = IssueService(session)
    try:
        return svc.create_issue(data)
    except Exception as e:
        logger.exception("Failed to create issue")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{issue_id}", response_model=IssueRead)
def get_issue(
    request: Request,
    issue_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("issue.read", "*", "issue"),
):
    """Get issue by ID."""
    svc = IssueService(session)
    issue = svc.get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    data = issue.model_dump()
    data = filter_single_response(
        request, session, "issue", data, project_id=issue.project_id
    )
    return IssueRead.model_validate(strip_field_security_metadata(data))


@router.get("/key/{key}", response_model=IssueRead)
def get_issue_by_key(
    request: Request,
    key: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("issue.read", "*", "issue"),
):
    """Get issue by key (e.g. ENG-1024)."""
    svc = IssueService(session)
    issue = svc.get_issue_by_key(key)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    data = issue.model_dump()
    data = filter_single_response(
        request, session, "issue", data, project_id=issue.project_id
    )
    return IssueRead.model_validate(strip_field_security_metadata(data))


@router.patch("/{issue_id}", response_model=IssueRead)
def update_issue(
    request: Request,
    issue_id: str,
    data: IssueUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("issue.update", "*", "issue"),
):
    """Update an issue."""
    svc = IssueService(session)
    issue = svc.get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    # Check field-level write permissions for any fields being updated
    update_fields = data.model_dump(exclude_unset=True)
    for field_key in update_fields:
        if not check_field_editable(
            request, session, "issue", field_key, project_id=issue.project_id
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Field '{field_key}' is not editable for your role",
            )
    updated = svc.update_issue(issue_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Issue not found")
    return updated


@router.delete("/{issue_id}", status_code=204)
def delete_issue(
    issue_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("issue.delete", "*", "issue"),
):
    """Archive (soft-delete) an issue."""
    svc = IssueService(session)
    if not svc.delete_issue(issue_id):
        raise HTTPException(status_code=404, detail="Issue not found")


@router.post("/{issue_id}/transition", response_model=IssueRead)
def transition_issue(
    issue_id: str,
    data: IssueTransition,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("issue.update", "*", "issue"),
):
    """Transition an issue to a new status."""
    svc = IssueService(session)
    issue = svc.transition_issue(issue_id, data)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


@router.get("/{issue_id}/transitions")
def get_available_transitions(
    issue_id: str,
    session: Session = Depends(_get_session),
):
    """Get available status transitions for an issue."""
    svc = IssueService(session)
    return svc.get_available_transitions(issue_id)


@router.post("/bulk/update")
def bulk_update_issues(
    data: IssueBulkUpdate,
    session: Session = Depends(_get_session),
):
    """Bulk update multiple issues."""
    svc = IssueService(session)
    count = svc.bulk_update(data)
    return {"updated": count}


@router.post("/{issue_id}/links", response_model=IssueLinkRead)
def link_issues(
    issue_id: str,
    data: IssueLinkCreate,
    session: Session = Depends(_get_session),
):
    """Create a link between two issues."""
    svc = IssueService(session)
    link = svc.link_issues(issue_id, data.target_issue_id, data.link_type)
    return link


@router.get("/{issue_id}/links")
def get_linked_issues(
    issue_id: str,
    session: Session = Depends(_get_session),
):
    """Get all linked issues."""
    svc = IssueService(session)
    return svc.get_linked_issues(issue_id)


@router.post("/{issue_id}/comments", response_model=CommentRead, status_code=201)
def add_comment(
    issue_id: str,
    data: CommentCreate,
    session: Session = Depends(_get_session),
):
    """Add a comment to an issue."""
    svc = IssueService(session)
    return svc.add_comment(issue_id, data)


@router.get("/{issue_id}/comments", response_model=List[CommentRead])
def list_comments(
    issue_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(_get_session),
):
    """List comments for an issue."""
    svc = IssueService(session)
    return svc.list_comments(issue_id, limit=limit, offset=offset)


@router.get("/{issue_id}/activity", response_model=List[ActivityRead])
def get_issue_activity(
    issue_id: str,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(_get_session),
):
    """Get activity log for an issue."""
    from common_lib.modules.project_management.activity import ActivityRepository

    repo = ActivityRepository(session)
    return repo.get_issue_activity(issue_id, limit=limit)


# ===========================================================================
# Multi-Level Task Hierarchy (04.05)
# ===========================================================================


@router.get("/{issue_id}/hierarchy")
def get_issue_hierarchy(
    issue_id: str,
    session: Session = Depends(_get_session),
):
    """Get full n-level hierarchy tree for an issue (ancestors + descendants)."""
    from common_lib.modules.project_management.issues.service import IssueService

    svc = IssueService(session)
    hierarchy = svc.get_hierarchy_tree(issue_id)
    if not hierarchy:
        raise HTTPException(status_code=404, detail="Issue not found")
    return hierarchy


@router.get("/{issue_id}/descendants")
def get_issue_descendants(
    issue_id: str,
    max_depth: int = Query(10, ge=1, le=20),
    session: Session = Depends(_get_session),
):
    """Get all descendants of an issue at all levels."""
    from common_lib.modules.project_management.issues.service import IssueService

    svc = IssueService(session)
    descendants = svc.get_descendants(issue_id, max_depth=max_depth)
    return {"items": descendants, "total": len(descendants)}


@router.get("/{issue_id}/ancestors")
def get_issue_ancestors(
    issue_id: str,
    session: Session = Depends(_get_session),
):
    """Get all ancestors of an issue (root -> immediate parent)."""
    from common_lib.modules.project_management.issues.service import IssueService

    svc = IssueService(session)
    ancestors = svc.get_ancestors(issue_id)
    return {"items": ancestors, "total": len(ancestors)}


# ===========================================================================
# Recurring Tasks (04.09)
# ===========================================================================


@router.post("/recurring/configs", status_code=201)
def create_recurring_task_config(
    data: TaskRecurrenceCreate,
    session: Session = Depends(_get_session),
):
    """Create a recurring task configuration from a template issue."""
    from common_lib.modules.project_management.issues.service import IssueService

    svc = IssueService(session)
    config = svc.create_recurring_task_config(
        template_issue_id=data.template_issue_id,
        recurrence_type=data.recurrence_type,
        interval=data.interval,
        days_of_week=data.days_of_week,
        day_of_month=data.day_of_month,
        cron_expression=data.cron_expression,
        start_date=data.start_date,
        end_date=data.end_date,
        max_occurrences=data.max_occurrences,
        copy_assignee=data.copy_assignee,
    )
    return config


@router.get("/recurring/configs")
def list_recurring_task_configs(
    project_id: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
):
    """List recurring task configurations."""
    from common_lib.modules.project_management.issues.service import IssueService

    svc = IssueService(session)
    configs = svc.list_recurring_task_configs(project_id=project_id)
    return {"items": [c.model_dump() for c in configs], "total": len(configs)}


@router.get("/recurring/configs/{config_id}")
def get_recurring_task_config(
    config_id: str,
    session: Session = Depends(_get_session),
):
    """Get a recurring task configuration by ID."""
    from common_lib.modules.project_management.issues.service import IssueService

    svc = IssueService(session)
    config = svc.get_recurring_task_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Recurrence config not found")
    return config


@router.patch("/recurring/configs/{config_id}")
def update_recurring_task_config(
    config_id: str,
    data: dict,
    session: Session = Depends(_get_session),
):
    """Update a recurring task configuration."""
    from common_lib.modules.project_management.issues.service import IssueService

    svc = IssueService(session)
    config = svc.update_recurring_task_config(config_id, data)
    if not config:
        raise HTTPException(status_code=404, detail="Recurrence config not found")
    return config


@router.delete("/recurring/configs/{config_id}", status_code=204)
def delete_recurring_task_config(
    config_id: str,
    session: Session = Depends(_get_session),
):
    """Delete a recurring task configuration."""
    from common_lib.modules.project_management.issues.service import IssueService

    svc = IssueService(session)
    if not svc.delete_recurring_task_config(config_id):
        raise HTTPException(status_code=404, detail="Recurrence config not found")


@router.post("/recurring/configs/{config_id}/generate")
def generate_recurring_instances(
    config_id: str,
    count: int = Query(1, ge=1, le=10),
    session: Session = Depends(_get_session),
):
    """Generate N instances from a recurring task configuration."""
    from common_lib.modules.project_management.issues.service import IssueService

    svc = IssueService(session)
    instances = svc.generate_recurring_instances(config_id, count=count)
    return {"items": [i.model_dump() for i in instances], "count": len(instances)}


@router.post("/recurring/process-all")
def process_all_recurring_tasks(
    session: Session = Depends(_get_session),
    _perm: None = require_permission("issues.manage", "*", "issues"),
):
    """Process all active recurring tasks. Usually called by a cron job."""
    from common_lib.modules.project_management.issues.service import IssueService

    svc = IssueService(session)
    return svc.process_all_recurring_tasks()
