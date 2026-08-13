"""
PM Module — Templates Library Routes (Domain 24)

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


router = APIRouter(prefix="/templates", tags=["PM Templates Library"])


# ------------------------------------------------------------------ #
# Template CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_templates(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("templates.read", "*", "templates"),
):
    """List Template records."""
    from common_lib.modules.project_management.templates.service import TemplateService

    svc = TemplateService(session)
    items = svc.list_templates(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_template(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("templates.create", "*", "templates"),
):
    """Create a Template record."""
    from common_lib.modules.project_management.templates.service import TemplateService

    svc = TemplateService(session)
    row = svc.create_template(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{template_id}")
def get_template(
    template_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("templates.read", "*", "templates"),
):
    """Get a single Template by id."""
    from common_lib.modules.project_management.templates.service import TemplateService

    svc = TemplateService(session)
    row = svc.get_template(template_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{template_id}")
def update_template(
    template_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("templates.update", "*", "templates"),
):
    """Update a Template record (partial)."""
    from common_lib.modules.project_management.templates.service import TemplateService

    svc = TemplateService(session)
    row = svc.update_template(template_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{template_id}")
def delete_template(
    template_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("templates.delete", "*", "templates"),
):
    """Delete a Template record."""
    from common_lib.modules.project_management.templates.service import TemplateService

    svc = TemplateService(session)
    svc.delete_template(template_id)
    return {"ok": True}


@router.post("/{template_id}/record-usage")
def record_usage(
    template_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("templates.update", "*", "templates"),
):
    """Increment usage count for a template."""
    from common_lib.modules.project_management.templates.service import TemplateService

    svc = TemplateService(session)
    kwargs = dict(data or {})
    kwargs['template_id'] = template_id
    result = svc.record_usage(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{template_id}/instantiate-template")
def instantiate_template(
    template_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("templates.update", "*", "templates"),
):
    """Instantiate a template into a concrete title + payload dict."""
    from common_lib.modules.project_management.templates.service import TemplateService

    svc = TemplateService(session)
    kwargs = dict(data or {})
    kwargs['template_id'] = template_id
    result = svc.instantiate_template(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{template_type}/list-categories")
def list_categories(
    template_type: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("templates.update", "*", "templates"),
):
    """List distinct template categories."""
    from common_lib.modules.project_management.templates.service import TemplateService

    svc = TemplateService(session)
    kwargs = dict(data or {})
    kwargs['template_type'] = template_type
    result = svc.list_categories(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
