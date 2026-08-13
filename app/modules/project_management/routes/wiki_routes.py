"""
PM Module — Wiki & Page Engine (Confluence Core) Routes (Domain 21)

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


router = APIRouter(prefix="/wiki", tags=["PM Wiki & Page Engine (Confluence Core)"])


# ------------------------------------------------------------------ #
# WikiPage CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_pages(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("wiki.read", "*", "wiki"),
):
    """List WikiPage records."""
    from common_lib.modules.project_management.wiki.service import WikiService

    svc = WikiService(session)
    items = svc.list_pages(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_page(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("wiki.create", "*", "wiki"),
):
    """Create a WikiPage record."""
    from common_lib.modules.project_management.wiki.service import WikiService

    svc = WikiService(session)
    row = svc.create_page(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{page_id}")
def get_page(
    page_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("wiki.read", "*", "wiki"),
):
    """Get a single WikiPage by id."""
    from common_lib.modules.project_management.wiki.service import WikiService

    svc = WikiService(session)
    row = svc.get_page(page_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{page_id}")
def update_page(
    page_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("wiki.update", "*", "wiki"),
):
    """Update a WikiPage record (partial)."""
    from common_lib.modules.project_management.wiki.service import WikiService

    svc = WikiService(session)
    row = svc.update_page(page_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{page_id}")
def delete_page(
    page_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("wiki.delete", "*", "wiki"),
):
    """Delete a WikiPage record."""
    from common_lib.modules.project_management.wiki.service import WikiService

    svc = WikiService(session)
    svc.delete_page(page_id)
    return {"ok": True}


@router.post("/{space_id}/get-page-tree")
def get_page_tree(
    space_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("wiki.update", "*", "wiki"),
):
    """Build a hierarchical page tree for a space."""
    from common_lib.modules.project_management.wiki.service import WikiService

    svc = WikiService(session)
    kwargs = dict(data or {})
    kwargs['space_id'] = space_id
    result = svc.get_page_tree(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{page_id}/archive-page")
def archive_page(
    page_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("wiki.update", "*", "wiki"),
):
    """Mark a page as archived."""
    from common_lib.modules.project_management.wiki.service import WikiService

    svc = WikiService(session)
    kwargs = dict(data or {})
    kwargs['page_id'] = page_id
    result = svc.archive_page(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{page_id}/get-version-history")
def get_version_history(
    page_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("wiki.update", "*", "wiki"),
):
    """List all revisions of a page."""
    from common_lib.modules.project_management.wiki.service import WikiService

    svc = WikiService(session)
    kwargs = dict(data or {})
    kwargs['page_id'] = page_id
    result = svc.get_version_history(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
