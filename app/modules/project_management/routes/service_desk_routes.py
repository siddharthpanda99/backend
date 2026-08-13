"""
PM Module — Service Desk & Helpdesk Routes (Domain 41)

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


router = APIRouter(prefix="/service_desk", tags=["PM Service Desk & Helpdesk"])


# ------------------------------------------------------------------ #
# RequestType CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_request_types(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("service_desk.read", "*", "service_desk"),
):
    """List RequestType records."""
    from common_lib.modules.project_management.service_desk.service import ServiceDeskService

    svc = ServiceDeskService(session)
    items = svc.list_request_types(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_request_type(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("service_desk.create", "*", "service_desk"),
):
    """Create a RequestType record."""
    from common_lib.modules.project_management.service_desk.service import ServiceDeskService

    svc = ServiceDeskService(session)
    row = svc.create_request_type(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{request_type_id}")
def get_request_type(
    request_type_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("service_desk.read", "*", "service_desk"),
):
    """Get a single RequestType by id."""
    from common_lib.modules.project_management.service_desk.service import ServiceDeskService

    svc = ServiceDeskService(session)
    row = svc.get_request_type(request_type_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{request_type_id}")
def update_request_type(
    request_type_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("service_desk.update", "*", "service_desk"),
):
    """Update a RequestType record (partial)."""
    from common_lib.modules.project_management.service_desk.service import ServiceDeskService

    svc = ServiceDeskService(session)
    row = svc.update_request_type(request_type_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{request_type_id}")
def delete_request_type(
    request_type_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("service_desk.delete", "*", "service_desk"),
):
    """Delete a RequestType record."""
    from common_lib.modules.project_management.service_desk.service import ServiceDeskService

    svc = ServiceDeskService(session)
    svc.delete_request_type(request_type_id)
    return {"ok": True}
