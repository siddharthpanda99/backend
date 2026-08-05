"""
PM Collaboration — REST Routes for Domain 15.

Endpoints:
- Mentions: GET /mentions/user/{user_id}, GET /mentions/entity, POST /mentions/parse, POST /mentions/{id}/read
- Whiteboards: CRUD at /whiteboards, canvas update
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collaboration", tags=["project_management", "collaboration"])


# ===========================================================================
# Mentions — 15.02
# ===========================================================================

def _get_mentions_service(session: Session):
    from common_lib.modules.project_management.collaboration.service import MentionsService
    return MentionsService(session=session)


def _get_whiteboard_service(session: Session):
    from common_lib.modules.project_management.collaboration.service import WhiteboardService
    return WhiteboardService(session=session)


@router.post("/mentions/parse")
def parse_mentions(
    text: str = Query(..., description="Text to parse for @mentions"),
    entity_type: str = Query(..., description="Entity type: comment, issue_description, standup"),
    entity_id: str = Query(..., description="Entity ID"),
    mentioned_by: str = Query("system", description="User who wrote the text"),
    _perm: None = require_permission("mention.create", "*", "mention"),
    session: Session = Depends(_get_session),
):
    """Parse @mentions from text and store them."""
    svc = _get_mentions_service(session)
    return svc.parse_mentions(text=text, entity_type=entity_type,
                              entity_id=entity_id, mentioned_by=mentioned_by)


@router.get("/mentions/user/{user_id}")
def get_mentions_for_user(
    user_id: str,
    limit: int = Query(50),
    offset: int = Query(0),
    _perm: None = require_permission("mention.read", "*", "mention"),
    session: Session = Depends(_get_session),
):
    """Get all @mentions for a specific user."""
    svc = _get_mentions_service(session)
    return svc.get_mentions_for_user(user_id=user_id, limit=limit, offset=offset)


@router.get("/mentions/entity")
def get_mentions_for_entity(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    _perm: None = require_permission("mention.read", "*", "mention"),
    session: Session = Depends(_get_session),
):
    """Get all @mentions within a specific entity."""
    svc = _get_mentions_service(session)
    return svc.get_mentions_for_entity(entity_type=entity_type, entity_id=entity_id)


@router.post("/mentions/{mention_id}/read")
def mark_mention_read(
    mention_id: str,
    _perm: None = require_permission("mention.update", "*", "mention"),
    session: Session = Depends(_get_session),
):
    """Mark a mention as read/resolved."""
    svc = _get_mentions_service(session)
    if not svc.mark_mention_read(mention_id):
        raise HTTPException(status_code=404, detail=f"Mention {mention_id} not found")
    return {"success": True, "mention_id": mention_id}


# ===========================================================================
# Whiteboards — 15.07
# ===========================================================================

@router.post("/whiteboards", status_code=201)
def create_whiteboard(
    project_id: str = Query(...),
    name: str = Query(...),
    description: Optional[str] = Query(None),
    created_by: str = Query("system"),
    _perm: None = require_permission("whiteboard.create", "*", "whiteboard"),
    session: Session = Depends(_get_session),
):
    """Create a new whiteboard."""
    svc = _get_whiteboard_service(session)
    wb = svc.create_whiteboard(project_id=project_id, name=name,
                               description=description, created_by=created_by)
    return wb.model_dump()


@router.get("/whiteboards")
def list_whiteboards(
    project_id: str = Query(...),
    limit: int = Query(50),
    offset: int = Query(0),
    _perm: None = require_permission("whiteboard.read", "*", "whiteboard"),
    session: Session = Depends(_get_session),
):
    """List whiteboards in a project."""
    svc = _get_whiteboard_service(session)
    return svc.list_whiteboards(project_id=project_id, limit=limit, offset=offset)


@router.get("/whiteboards/{whiteboard_id}")
def get_whiteboard(
    whiteboard_id: str,
    _perm: None = require_permission("whiteboard.read", "*", "whiteboard"),
    session: Session = Depends(_get_session),
):
    """Get a whiteboard by ID with full canvas data."""
    svc = _get_whiteboard_service(session)
    wb = svc.get_whiteboard(whiteboard_id)
    if not wb:
        raise HTTPException(status_code=404, detail=f"Whiteboard {whiteboard_id} not found")
    return wb.model_dump()


@router.put("/whiteboards/{whiteboard_id}/canvas")
def update_whiteboard_canvas(
    whiteboard_id: str,
    canvas_data: dict,
    updated_by: Optional[str] = Query(None),
    _perm: None = require_permission("whiteboard.update", "*", "whiteboard"),
    session: Session = Depends(_get_session),
):
    """Update a whiteboard's canvas data."""
    svc = _get_whiteboard_service(session)
    wb = svc.update_canvas(whiteboard_id=whiteboard_id, canvas_data=canvas_data,
                           updated_by=updated_by)
    if not wb:
        raise HTTPException(status_code=404, detail=f"Whiteboard {whiteboard_id} not found")
    return wb.model_dump()


@router.delete("/whiteboards/{whiteboard_id}")
def delete_whiteboard(
    whiteboard_id: str,
    _perm: None = require_permission("whiteboard.delete", "*", "whiteboard"),
    session: Session = Depends(_get_session),
):
    """Delete a whiteboard."""
    svc = _get_whiteboard_service(session)
    if not svc.delete_whiteboard(whiteboard_id):
        raise HTTPException(status_code=404, detail=f"Whiteboard {whiteboard_id} not found")
    return {"success": True, "whiteboard_id": whiteboard_id}
