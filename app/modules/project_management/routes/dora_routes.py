"""
PM Module — DevOps Metrics & DORA Routes (Domain 39)

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


router = APIRouter(prefix="/dora", tags=["PM DevOps Metrics & DORA"])


# ------------------------------------------------------------------ #
# DoraMetric CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_metrics(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dora.read", "*", "dora"),
):
    """List DoraMetric records."""
    from common_lib.modules.project_management.dora.service import DoraService

    svc = DoraService(session)
    items = svc.list_metrics(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_metric(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dora.create", "*", "dora"),
):
    """Create a DoraMetric record."""
    from common_lib.modules.project_management.dora.service import DoraService

    svc = DoraService(session)
    row = svc.create_metric(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{metric_id}")
def get_metric(
    metric_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dora.read", "*", "dora"),
):
    """Get a single DoraMetric by id."""
    from common_lib.modules.project_management.dora.service import DoraService

    svc = DoraService(session)
    row = svc.get_metric(metric_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{metric_id}")
def update_metric(
    metric_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dora.update", "*", "dora"),
):
    """Update a DoraMetric record (partial)."""
    from common_lib.modules.project_management.dora.service import DoraService

    svc = DoraService(session)
    row = svc.update_metric(metric_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{metric_id}")
def delete_metric(
    metric_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dora.delete", "*", "dora"),
):
    """Delete a DoraMetric record."""
    from common_lib.modules.project_management.dora.service import DoraService

    svc = DoraService(session)
    svc.delete_metric(metric_id)
    return {"ok": True}


@router.post("/{project_id}/compute-metrics")
def compute_metrics(
    project_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dora.update", "*", "dora"),
):
    """Compute DORA metrics for a project/period from caller-provided counts (deployments, failures, lead time)."""
    from common_lib.modules.project_management.dora.service import DoraService

    svc = DoraService(session)
    kwargs = dict(data or {})
    kwargs['project_id'] = project_id
    result = svc.compute_metrics(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
