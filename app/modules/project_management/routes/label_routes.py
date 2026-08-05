"""
PM Label Routes — Issue/project labels CRUD.

RBAC permissions: label.read, label.create, label.update, label.delete
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session
from pydantic import BaseModel

from app.modules.auth.dependencies import require_permission

router = APIRouter(prefix="/labels", tags=["project_management", "labels"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class LabelCreate(BaseModel):
    name: str
    color: str = "#6366f1"


class LabelUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


@router.get("")
def list_labels(
    project_id: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("label.read", "*", "label"),
):
    """List all labels for a project."""
    from common_lib.modules.project_management.labels.service import LabelService
    svc = LabelService(session)
    labels = svc.list_labels(project_id=project_id)
    return {"items": [l.model_dump() for l in labels], "total": len(labels)}


@router.post("", status_code=201)
def create_label(
    data: LabelCreate,
    project_id: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("label.create", "*", "label"),
):
    """Create a new label."""
    from common_lib.modules.project_management.labels.service import LabelService
    svc = LabelService(session)
    label = svc.create_label(name=data.name, color=data.color, project_id=project_id)
    return label.model_dump()


@router.put("/{label_id}")
def update_label(
    label_id: str,
    data: LabelUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("label.update", "*", "label"),
):
    """Update a label."""
    from common_lib.modules.project_management.labels.service import LabelService
    svc = LabelService(session)
    label = svc.update_label(label_id, data.model_dump(exclude_unset=True))
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")
    return label.model_dump()


@router.delete("/{label_id}", status_code=204)
def delete_label(
    label_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("label.delete", "*", "label"),
):
    """Delete a label."""
    from common_lib.modules.project_management.labels.service import LabelService
    svc = LabelService(session)
    if not svc.delete_label(label_id):
        raise HTTPException(status_code=404, detail="Label not found")
    return None
