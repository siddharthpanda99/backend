"""Saved Filter API Routes — CRUD for saved search filters."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.schemas import (
    SavedFilterCreate, SavedFilterUpdate, SavedFilterRead,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/saved-filters", tags=["project_management", "saved_filters"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.post("", response_model=SavedFilterRead, status_code=201)
def create_filter(data: SavedFilterCreate, session: Session = Depends(_get_session),
    _perm: None = require_permission("saved_filter.create", "*", "saved_filter"),):
    """Create a saved filter."""
    from common_lib.modules.project_management.saved_filters.service import SavedFilterService
    svc = SavedFilterService(session)
    try:
        return svc.create_filter(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[SavedFilterRead])
def list_filters(session: Session = Depends(_get_session),
    _perm: None = require_permission("saved_filter.read", "*", "saved_filter"),):
    """List all saved filters (use query params in the caller)."""
    from common_lib.modules.project_management.saved_filters.service import SavedFilterService
    svc = SavedFilterService(session)
    return svc.list_all()


@router.get("/{filter_id}", response_model=SavedFilterRead)
def get_filter(filter_id: str, session: Session = Depends(_get_session),
    _perm: None = require_permission("saved_filter.read", "*", "saved_filter"),):
    """Get a single saved filter by ID."""
    from common_lib.modules.project_management.saved_filters.service import SavedFilterService
    svc = SavedFilterService(session)
    f = svc.get_filter(filter_id)
    if not f:
        raise HTTPException(status_code=404, detail="Saved filter not found")
    return f


@router.put("/{filter_id}", response_model=SavedFilterRead)
def update_filter(filter_id: str, data: SavedFilterUpdate, session: Session = Depends(_get_session),
    _perm: None = require_permission("saved_filter.update", "*", "saved_filter"),):
    """Update a saved filter."""
    from common_lib.modules.project_management.saved_filters.service import SavedFilterService
    svc = SavedFilterService(session)
    f = svc.update_filter(filter_id, data)
    if not f:
        raise HTTPException(status_code=404, detail="Saved filter not found")
    return f


@router.delete("/{filter_id}", status_code=204)
def delete_filter(filter_id: str, session: Session = Depends(_get_session),
    _perm: None = require_permission("saved_filter.delete", "*", "saved_filter"),):
    """Delete a saved filter."""
    from common_lib.modules.project_management.saved_filters.service import SavedFilterService
    svc = SavedFilterService(session)
    success = svc.delete_filter(filter_id)
    if not success:
        raise HTTPException(status_code=404, detail="Saved filter not found")
    return None
