"""
PM Module — Admin, Billing & Enterprise Controls Routes (Domain 50)

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


router = APIRouter(prefix="/admin_billing", tags=["PM Admin, Billing & Enterprise Controls"])


# ------------------------------------------------------------------ #
# AuditLog CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_logs(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("admin_billing.read", "*", "admin_billing"),
):
    """List AuditLog records."""
    from common_lib.modules.project_management.admin_billing.service import AdminBillingService

    svc = AdminBillingService(session)
    items = svc.list_logs(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_log(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("admin_billing.create", "*", "admin_billing"),
):
    """Create a AuditLog record."""
    from common_lib.modules.project_management.admin_billing.service import AdminBillingService

    svc = AdminBillingService(session)
    row = svc.create_log(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{log_id}")
def get_log(
    log_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("admin_billing.read", "*", "admin_billing"),
):
    """Get a single AuditLog by id."""
    from common_lib.modules.project_management.admin_billing.service import AdminBillingService

    svc = AdminBillingService(session)
    row = svc.get_log(log_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{log_id}")
def update_log(
    log_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("admin_billing.update", "*", "admin_billing"),
):
    """Update a AuditLog record (partial)."""
    from common_lib.modules.project_management.admin_billing.service import AdminBillingService

    svc = AdminBillingService(session)
    row = svc.update_log(log_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{log_id}")
def delete_log(
    log_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("admin_billing.delete", "*", "admin_billing"),
):
    """Delete a AuditLog record."""
    from common_lib.modules.project_management.admin_billing.service import AdminBillingService

    svc = AdminBillingService(session)
    svc.delete_log(log_id)
    return {"ok": True}


@router.post("/{workspace_id}/log-action")
def log_action(
    workspace_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("admin_billing.update", "*", "admin_billing"),
):
    """Write an audit log entry."""
    from common_lib.modules.project_management.admin_billing.service import AdminBillingService

    svc = AdminBillingService(session)
    kwargs = dict(data or {})
    kwargs['workspace_id'] = workspace_id
    result = svc.log_action(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{workspace_id}/get-usage-report")
def get_usage_report(
    workspace_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("admin_billing.update", "*", "admin_billing"),
):
    """Aggregate workspace usage (seats, active users, storage units)."""
    from common_lib.modules.project_management.admin_billing.service import AdminBillingService

    svc = AdminBillingService(session)
    kwargs = dict(data or {})
    kwargs['workspace_id'] = workspace_id
    result = svc.get_usage_report(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
