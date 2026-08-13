"""
PM Module — Customer Portal Routes (Domain 42)

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


router = APIRouter(prefix="/customer_portal", tags=["PM Customer Portal"])


# ------------------------------------------------------------------ #
# PortalConfig CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_configs(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("customer_portal.read", "*", "customer_portal"),
):
    """List PortalConfig records."""
    from common_lib.modules.project_management.customer_portal.service import CustomerPortalService

    svc = CustomerPortalService(session)
    items = svc.list_configs(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_config(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("customer_portal.create", "*", "customer_portal"),
):
    """Create a PortalConfig record."""
    from common_lib.modules.project_management.customer_portal.service import CustomerPortalService

    svc = CustomerPortalService(session)
    row = svc.create_config(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{config_id}")
def get_config(
    config_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("customer_portal.read", "*", "customer_portal"),
):
    """Get a single PortalConfig by id."""
    from common_lib.modules.project_management.customer_portal.service import CustomerPortalService

    svc = CustomerPortalService(session)
    row = svc.get_config(config_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{config_id}")
def update_config(
    config_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("customer_portal.update", "*", "customer_portal"),
):
    """Update a PortalConfig record (partial)."""
    from common_lib.modules.project_management.customer_portal.service import CustomerPortalService

    svc = CustomerPortalService(session)
    row = svc.update_config(config_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{config_id}")
def delete_config(
    config_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("customer_portal.delete", "*", "customer_portal"),
):
    """Delete a PortalConfig record."""
    from common_lib.modules.project_management.customer_portal.service import CustomerPortalService

    svc = CustomerPortalService(session)
    svc.delete_config(config_id)
    return {"ok": True}


@router.post("/{config_id}/submit-ticket")
def submit_ticket(
    config_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("customer_portal.update", "*", "customer_portal"),
):
    """Create a customer portal ticket (guest submit)."""
    from common_lib.modules.project_management.customer_portal.service import CustomerPortalService

    svc = CustomerPortalService(session)
    kwargs = dict(data or {})
    kwargs['config_id'] = config_id
    result = svc.submit_ticket(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{ticket_id}/add-customer-comment")
def add_customer_comment(
    ticket_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("customer_portal.update", "*", "customer_portal"),
):
    """Append a customer comment to a portal ticket."""
    from common_lib.modules.project_management.customer_portal.service import CustomerPortalService

    svc = CustomerPortalService(session)
    kwargs = dict(data or {})
    kwargs['ticket_id'] = ticket_id
    result = svc.add_customer_comment(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
