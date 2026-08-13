"""
PM Module — Page Macros & Embeds Routes (Domain 25)

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


router = APIRouter(prefix="/macros", tags=["PM Page Macros & Embeds"])


# ------------------------------------------------------------------ #
# PageMacro CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_macros(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("macros.read", "*", "macros"),
):
    """List PageMacro records."""
    from common_lib.modules.project_management.macros.service import MacroService

    svc = MacroService(session)
    items = svc.list_macros(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_macro(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("macros.create", "*", "macros"),
):
    """Create a PageMacro record."""
    from common_lib.modules.project_management.macros.service import MacroService

    svc = MacroService(session)
    row = svc.create_macro(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{macro_id}")
def get_macro(
    macro_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("macros.read", "*", "macros"),
):
    """Get a single PageMacro by id."""
    from common_lib.modules.project_management.macros.service import MacroService

    svc = MacroService(session)
    row = svc.get_macro(macro_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{macro_id}")
def update_macro(
    macro_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("macros.update", "*", "macros"),
):
    """Update a PageMacro record (partial)."""
    from common_lib.modules.project_management.macros.service import MacroService

    svc = MacroService(session)
    row = svc.update_macro(macro_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{macro_id}")
def delete_macro(
    macro_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("macros.delete", "*", "macros"),
):
    """Delete a PageMacro record."""
    from common_lib.modules.project_management.macros.service import MacroService

    svc = MacroService(session)
    svc.delete_macro(macro_id)
    return {"ok": True}


@router.post("/{page_id}/render-macro")
def render_macro(
    page_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("macros.update", "*", "macros"),
):
    """Render a macro to its output payload (builtin registry)."""
    from common_lib.modules.project_management.macros.service import MacroService

    svc = MacroService(session)
    kwargs = dict(data or {})
    kwargs['page_id'] = page_id
    result = svc.render_macro(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
