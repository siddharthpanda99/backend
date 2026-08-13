"""
PM Module — Space Management Routes (Domain 23)

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


router = APIRouter(prefix="/spaces", tags=["PM Space Management"])


# ------------------------------------------------------------------ #
# WikiSpace CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_spaces(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("spaces.read", "*", "spaces"),
):
    """List WikiSpace records."""
    from common_lib.modules.project_management.spaces.service import SpaceService

    svc = SpaceService(session)
    items = svc.list_spaces(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_space(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("spaces.create", "*", "spaces"),
):
    """Create a WikiSpace record."""
    from common_lib.modules.project_management.spaces.service import SpaceService

    svc = SpaceService(session)
    row = svc.create_space(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{space_id}")
def get_space(
    space_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("spaces.read", "*", "spaces"),
):
    """Get a single WikiSpace by id."""
    from common_lib.modules.project_management.spaces.service import SpaceService

    svc = SpaceService(session)
    row = svc.get_space(space_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{space_id}")
def update_space(
    space_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("spaces.update", "*", "spaces"),
):
    """Update a WikiSpace record (partial)."""
    from common_lib.modules.project_management.spaces.service import SpaceService

    svc = SpaceService(session)
    row = svc.update_space(space_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{space_id}")
def delete_space(
    space_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("spaces.delete", "*", "spaces"),
):
    """Delete a WikiSpace record."""
    from common_lib.modules.project_management.spaces.service import SpaceService

    svc = SpaceService(session)
    svc.delete_space(space_id)
    return {"ok": True}


@router.post("/{space_id}/set-homepage")
def set_homepage(
    space_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("spaces.update", "*", "spaces"),
):
    """Set the homepage page for a space."""
    from common_lib.modules.project_management.spaces.service import SpaceService

    svc = SpaceService(session)
    kwargs = dict(data or {})
    kwargs['space_id'] = space_id
    result = svc.set_homepage(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{space_id}/get-space-analytics")
def get_space_analytics(
    space_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("spaces.update", "*", "spaces"),
):
    """Return basic analytics for a space (page count, contributors)."""
    from common_lib.modules.project_management.spaces.service import SpaceService

    svc = SpaceService(session)
    kwargs = dict(data or {})
    kwargs['space_id'] = space_id
    result = svc.get_space_analytics(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{space_id}/link-project")
def link_project(
    space_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("spaces.update", "*", "spaces"),
):
    """Link a project to a space via settings."""
    from common_lib.modules.project_management.spaces.service import SpaceService

    svc = SpaceService(session)
    kwargs = dict(data or {})
    kwargs['space_id'] = space_id
    result = svc.link_project(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
