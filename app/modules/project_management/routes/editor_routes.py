"""
PM Module — Rich Text Editor Routes (Domain 22)

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


router = APIRouter(prefix="/editor", tags=["PM Rich Text Editor"])


# ------------------------------------------------------------------ #
# EditorDraft CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_drafts(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("editor.read", "*", "editor"),
):
    """List EditorDraft records."""
    from common_lib.modules.project_management.editor.service import EditorService

    svc = EditorService(session)
    items = svc.list_drafts(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_draft(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("editor.create", "*", "editor"),
):
    """Create a EditorDraft record."""
    from common_lib.modules.project_management.editor.service import EditorService

    svc = EditorService(session)
    row = svc.create_draft(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{draft_id}")
def get_draft(
    draft_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("editor.read", "*", "editor"),
):
    """Get a single EditorDraft by id."""
    from common_lib.modules.project_management.editor.service import EditorService

    svc = EditorService(session)
    row = svc.get_draft(draft_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{draft_id}")
def update_draft(
    draft_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("editor.update", "*", "editor"),
):
    """Update a EditorDraft record (partial)."""
    from common_lib.modules.project_management.editor.service import EditorService

    svc = EditorService(session)
    row = svc.update_draft(draft_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{draft_id}")
def delete_draft(
    draft_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("editor.delete", "*", "editor"),
):
    """Delete a EditorDraft record."""
    from common_lib.modules.project_management.editor.service import EditorService

    svc = EditorService(session)
    svc.delete_draft(draft_id)
    return {"ok": True}


@router.post("/{page_id}/autosave")
def autosave(
    page_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("editor.update", "*", "editor"),
):
    """Persist an autosave draft for a page/user."""
    from common_lib.modules.project_management.editor.service import EditorService

    svc = EditorService(session)
    kwargs = dict(data or {})
    kwargs['page_id'] = page_id
    result = svc.autosave(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{page_id}/reorder-blocks")
def reorder_blocks(
    page_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("editor.update", "*", "editor"),
):
    """Reorder page blocks by a list of block ids."""
    from common_lib.modules.project_management.editor.service import EditorService

    svc = EditorService(session)
    kwargs = dict(data or {})
    kwargs['page_id'] = page_id
    result = svc.reorder_blocks(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
