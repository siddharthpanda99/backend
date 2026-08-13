"""
PM Module — API & Developer Platform Routes (Domain 49)

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


router = APIRouter(prefix="/developer_api", tags=["PM API & Developer Platform"])


# ------------------------------------------------------------------ #
# ApiToken CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_tokens(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("developer_api.read", "*", "developer_api"),
):
    """List ApiToken records."""
    from common_lib.modules.project_management.developer_api.service import DeveloperApiService

    svc = DeveloperApiService(session)
    items = svc.list_tokens(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_token(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("developer_api.create", "*", "developer_api"),
):
    """Create a ApiToken record."""
    from common_lib.modules.project_management.developer_api.service import DeveloperApiService

    svc = DeveloperApiService(session)
    row = svc.create_token(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{token_id}")
def get_token(
    token_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("developer_api.read", "*", "developer_api"),
):
    """Get a single ApiToken by id."""
    from common_lib.modules.project_management.developer_api.service import DeveloperApiService

    svc = DeveloperApiService(session)
    row = svc.get_token(token_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{token_id}")
def update_token(
    token_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("developer_api.update", "*", "developer_api"),
):
    """Update a ApiToken record (partial)."""
    from common_lib.modules.project_management.developer_api.service import DeveloperApiService

    svc = DeveloperApiService(session)
    row = svc.update_token(token_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{token_id}")
def delete_token(
    token_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("developer_api.delete", "*", "developer_api"),
):
    """Delete a ApiToken record."""
    from common_lib.modules.project_management.developer_api.service import DeveloperApiService

    svc = DeveloperApiService(session)
    svc.delete_token(token_id)
    return {"ok": True}


@router.post("/{token_id}/revoke-token")
def revoke_token(
    token_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("developer_api.update", "*", "developer_api"),
):
    """Revoke an API token."""
    from common_lib.modules.project_management.developer_api.service import DeveloperApiService

    svc = DeveloperApiService(session)
    kwargs = dict(data or {})
    kwargs['token_id'] = token_id
    result = svc.revoke_token(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{token_hash}/validate-token")
def validate_token(
    token_hash: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("developer_api.update", "*", "developer_api"),
):
    """Validate a token hash and return the token (None if invalid/revoked/expired)."""
    from common_lib.modules.project_management.developer_api.service import DeveloperApiService

    svc = DeveloperApiService(session)
    kwargs = dict(data or {})
    kwargs['token_hash'] = token_hash
    result = svc.validate_token(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{workspace_id}/get-usage-stats")
def get_usage_stats(
    workspace_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("developer_api.update", "*", "developer_api"),
):
    """Aggregate API usage stats per workspace."""
    from common_lib.modules.project_management.developer_api.service import DeveloperApiService

    svc = DeveloperApiService(session)
    kwargs = dict(data or {})
    kwargs['workspace_id'] = workspace_id
    result = svc.get_usage_stats(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
