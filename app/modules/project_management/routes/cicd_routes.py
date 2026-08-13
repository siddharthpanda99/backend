"""
PM Module — CI/CD & Deployment Tracking Routes (Domain 37)

REST API endpoints mounted in index.py.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from sqlmodel import Session

from app.modules.auth.dependencies.authz import require_permission


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


router = APIRouter(prefix="/cicd", tags=["PM CI/CD & Deployment Tracking"])


# ------------------------------------------------------------------ #
# Environment CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_environments(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("cicd.read", "*", "cicd"),
):
    """List Environment records."""
    from common_lib.modules.project_management.cicd.service import CicdService

    svc = CicdService(session)
    items = svc.list_environments(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_environment(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("cicd.create", "*", "cicd"),
):
    """Create a Environment record."""
    from common_lib.modules.project_management.cicd.service import CicdService

    svc = CicdService(session)
    row = svc.create_environment(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{environment_id}")
def get_environment(
    environment_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("cicd.read", "*", "cicd"),
):
    """Get a single Environment by id."""
    from common_lib.modules.project_management.cicd.service import CicdService

    svc = CicdService(session)
    row = svc.get_environment(environment_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{environment_id}")
def update_environment(
    environment_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("cicd.update", "*", "cicd"),
):
    """Update a Environment record (partial)."""
    from common_lib.modules.project_management.cicd.service import CicdService

    svc = CicdService(session)
    row = svc.update_environment(environment_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{environment_id}")
def delete_environment(
    environment_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("cicd.delete", "*", "cicd"),
):
    """Delete a Environment record."""
    from common_lib.modules.project_management.cicd.service import CicdService

    svc = CicdService(session)
    svc.delete_environment(environment_id)
    return {"ok": True}


@router.post("/{project_id}/get-issue-deployment-state")
def get_issue_deployment_state(
    project_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("cicd.update", "*", "cicd"),
):
    """Return deployment state for each environment (latest deployment per env)."""
    from common_lib.modules.project_management.cicd.service import CicdService

    svc = CicdService(session)
    kwargs = dict(data or {})
    kwargs['project_id'] = project_id
    result = svc.get_issue_deployment_state(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{project_id}/get-deployment-dashboard")
def get_deployment_dashboard(
    project_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("cicd.update", "*", "cicd"),
):
    """Recent deployments grouped by environment."""
    from common_lib.modules.project_management.cicd.service import CicdService

    svc = CicdService(session)
    kwargs = dict(data or {})
    kwargs['project_id'] = project_id
    result = svc.get_deployment_dashboard(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
