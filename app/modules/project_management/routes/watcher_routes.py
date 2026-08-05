"""Watcher API Routes — follow/unfollow issues and check watcher status."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.schemas import WatcherAdd, WatcherRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/issues/{issue_id}/watchers", tags=["project_management", "watchers"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.get("", response_model=list[WatcherRead])
def list_watchers(issue_id: str, session: Session = Depends(_get_session),
    _perm: None = require_permission("watcher.read", "*", "watcher"),):
    """List all watchers of an issue."""
    from common_lib.modules.project_management.watcher.service import WatcherService
    svc = WatcherService(session)
    return svc.list_watchers(issue_id)


@router.post("", response_model=WatcherRead, status_code=201)
def add_watcher(issue_id: str, data: WatcherAdd, session: Session = Depends(_get_session),
    _perm: None = require_permission("watcher.create", "*", "watcher"),):
    """Add a watcher to an issue."""
    from common_lib.modules.project_management.watcher.service import WatcherService
    svc = WatcherService(session)
    try:
        return svc.add_watcher(issue_id, data.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{user_id}", status_code=204)
def remove_watcher(issue_id: str, user_id: str, session: Session = Depends(_get_session),
    _perm: None = require_permission("watcher.delete", "*", "watcher"),):
    """Remove a watcher from an issue."""
    from common_lib.modules.project_management.watcher.service import WatcherService
    svc = WatcherService(session)
    success = svc.remove_watcher(issue_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Watcher not found")
    return None


@router.get("/{user_id}/check")
def is_watching(issue_id: str, user_id: str, session: Session = Depends(_get_session),
    _perm: None = require_permission("watcher.read", "*", "watcher"),):
    """Check if a user is watching an issue."""
    from common_lib.modules.project_management.watcher.service import WatcherService
    svc = WatcherService(session)
    watching = svc.is_watching(issue_id, user_id)
    return {"issue_id": issue_id, "user_id": user_id, "is_watching": watching}
