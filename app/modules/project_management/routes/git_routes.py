"""
PM Module — Git Integration Layer Routes (Domain 36)

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


router = APIRouter(prefix="/git", tags=["PM Git Integration Layer"])


# ------------------------------------------------------------------ #
# GitConnection CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_connections(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("git.read", "*", "git"),
):
    """List GitConnection records."""
    from common_lib.modules.project_management.git.service import GitService

    svc = GitService(session)
    items = svc.list_connections(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_connection(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("git.create", "*", "git"),
):
    """Create a GitConnection record."""
    from common_lib.modules.project_management.git.service import GitService

    svc = GitService(session)
    row = svc.create_connection(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{connection_id}")
def get_connection(
    connection_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("git.read", "*", "git"),
):
    """Get a single GitConnection by id."""
    from common_lib.modules.project_management.git.service import GitService

    svc = GitService(session)
    row = svc.get_connection(connection_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{connection_id}")
def update_connection(
    connection_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("git.update", "*", "git"),
):
    """Update a GitConnection record (partial)."""
    from common_lib.modules.project_management.git.service import GitService

    svc = GitService(session)
    row = svc.update_connection(connection_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{connection_id}")
def delete_connection(
    connection_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("git.delete", "*", "git"),
):
    """Delete a GitConnection record."""
    from common_lib.modules.project_management.git.service import GitService

    svc = GitService(session)
    svc.delete_connection(connection_id)
    return {"ok": True}


@router.post("/{issue_id}/link-ref")
def link_ref(
    issue_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("git.update", "*", "git"),
):
    """Link a git ref (branch/commit/PR/deployment) to an issue."""
    from common_lib.modules.project_management.git.service import GitService

    svc = GitService(session)
    kwargs = dict(data or {})
    kwargs['issue_id'] = issue_id
    result = svc.link_ref(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{issue_key}/create-branch-name")
def create_branch_name(
    issue_key: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("git.update", "*", "git"),
):
    """Build a conventional branch name from an issue key and title."""
    from common_lib.modules.project_management.git.service import GitService

    svc = GitService(session)
    kwargs = dict(data or {})
    kwargs['issue_key'] = issue_key
    result = svc.create_branch_name(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
