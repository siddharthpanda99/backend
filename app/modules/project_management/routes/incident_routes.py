"""
PM Module — Incident & On-Call Management Routes (Domain 40)

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


router = APIRouter(prefix="/incident", tags=["PM Incident & On-Call Management"])


# ------------------------------------------------------------------ #
# Incident CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_incidents(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("incident.read", "*", "incident"),
):
    """List Incident records."""
    from common_lib.modules.project_management.incident.service import IncidentService

    svc = IncidentService(session)
    items = svc.list_incidents(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_incident(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("incident.create", "*", "incident"),
):
    """Create a Incident record."""
    from common_lib.modules.project_management.incident.service import IncidentService

    svc = IncidentService(session)
    row = svc.create_incident(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{incident_id}")
def get_incident(
    incident_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("incident.read", "*", "incident"),
):
    """Get a single Incident by id."""
    from common_lib.modules.project_management.incident.service import IncidentService

    svc = IncidentService(session)
    row = svc.get_incident(incident_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{incident_id}")
def update_incident(
    incident_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("incident.update", "*", "incident"),
):
    """Update a Incident record (partial)."""
    from common_lib.modules.project_management.incident.service import IncidentService

    svc = IncidentService(session)
    row = svc.update_incident(incident_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{incident_id}")
def delete_incident(
    incident_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("incident.delete", "*", "incident"),
):
    """Delete a Incident record."""
    from common_lib.modules.project_management.incident.service import IncidentService

    svc = IncidentService(session)
    svc.delete_incident(incident_id)
    return {"ok": True}


@router.post("/{incident_id}/add-timeline-event")
def add_timeline_event(
    incident_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("incident.update", "*", "incident"),
):
    """Append a timeline event to an incident."""
    from common_lib.modules.project_management.incident.service import IncidentService

    svc = IncidentService(session)
    kwargs = dict(data or {})
    kwargs['incident_id'] = incident_id
    result = svc.add_timeline_event(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{incident_id}/resolve-incident")
def resolve_incident(
    incident_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("incident.update", "*", "incident"),
):
    """Mark an incident as resolved."""
    from common_lib.modules.project_management.incident.service import IncidentService

    svc = IncidentService(session)
    kwargs = dict(data or {})
    kwargs['incident_id'] = incident_id
    result = svc.resolve_incident(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
