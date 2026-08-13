"""
PM Module — Integration Hub & Webhooks Routes (Domain 48)

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


router = APIRouter(prefix="/integration_hub", tags=["PM Integration Hub & Webhooks"])


# ------------------------------------------------------------------ #
# Integration CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_integrations(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("integration_hub.read", "*", "integration_hub"),
):
    """List Integration records."""
    from common_lib.modules.project_management.integration_hub.service import IntegrationHubService

    svc = IntegrationHubService(session)
    items = svc.list_integrations(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_integration(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("integration_hub.create", "*", "integration_hub"),
):
    """Create a Integration record."""
    from common_lib.modules.project_management.integration_hub.service import IntegrationHubService

    svc = IntegrationHubService(session)
    row = svc.create_integration(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{integration_id}")
def get_integration(
    integration_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("integration_hub.read", "*", "integration_hub"),
):
    """Get a single Integration by id."""
    from common_lib.modules.project_management.integration_hub.service import IntegrationHubService

    svc = IntegrationHubService(session)
    row = svc.get_integration(integration_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{integration_id}")
def update_integration(
    integration_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("integration_hub.update", "*", "integration_hub"),
):
    """Update a Integration record (partial)."""
    from common_lib.modules.project_management.integration_hub.service import IntegrationHubService

    svc = IntegrationHubService(session)
    row = svc.update_integration(integration_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{integration_id}")
def delete_integration(
    integration_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("integration_hub.delete", "*", "integration_hub"),
):
    """Delete a Integration record."""
    from common_lib.modules.project_management.integration_hub.service import IntegrationHubService

    svc = IntegrationHubService(session)
    svc.delete_integration(integration_id)
    return {"ok": True}


@router.post("/{integration_id}/toggle-integration")
def toggle_integration(
    integration_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("integration_hub.update", "*", "integration_hub"),
):
    """Enable or disable an integration."""
    from common_lib.modules.project_management.integration_hub.service import IntegrationHubService

    svc = IntegrationHubService(session)
    kwargs = dict(data or {})
    kwargs['integration_id'] = integration_id
    result = svc.toggle_integration(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{webhook_id}/deliver-webhook")
def deliver_webhook(
    webhook_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("integration_hub.update", "*", "integration_hub"),
):
    """Queue a webhook delivery record (actual POST handled by delivery worker)."""
    from common_lib.modules.project_management.integration_hub.service import IntegrationHubService

    svc = IntegrationHubService(session)
    kwargs = dict(data or {})
    kwargs['webhook_id'] = webhook_id
    result = svc.deliver_webhook(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
