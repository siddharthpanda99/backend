"""
Unified Hooks Router

Thin FastAPI router for the unified hook definition system.
All CRUD + test endpoints.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.triggers.models import HookDefinitionDB

router = APIRouter(prefix="/hook-definitions", tags=["Unified Hooks"])


# ── Pydantic Schemas ────────────────────────────────────────────────


class HookDefinitionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    phase: str = "post"
    priority: int = 100
    blocking: bool = False
    hook_class: str
    hook_config: Optional[Dict[str, Any]] = None
    scope: str = "universal"
    enabled: bool = True
    conditions: Optional[Dict[str, Any]] = None
    tags: list[str] = []


class HookDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    phase: Optional[str] = None
    priority: Optional[int] = None
    blocking: Optional[bool] = None
    hook_class: Optional[str] = None
    hook_config: Optional[Dict[str, Any]] = None
    scope: Optional[str] = None
    enabled: Optional[bool] = None
    conditions: Optional[Dict[str, Any]] = None
    tags: Optional[list[str]] = None


class HookTestRequest(BaseModel):
    context: Dict[str, Any] = {}


# ── Serialiser ──────────────────────────────────────────────────────


def _hook_to_dict(h: HookDefinitionDB) -> dict:
    return {
        "id": h.id,
        "name": h.name,
        "description": h.description,
        "phase": h.phase,
        "priority": h.priority,
        "blocking": h.blocking,
        "hook_class": h.hook_class,
        "hook_config": json.loads(h.hook_config) if h.hook_config else {},
        "scope": h.scope,
        "enabled": h.enabled,
        "conditions": json.loads(h.conditions) if h.conditions else {},
        "tags": json.loads(h.tags) if h.tags else [],
        "created_at": h.created_at.isoformat() if h.created_at else None,
        "updated_at": h.updated_at.isoformat() if h.updated_at else None,
    }


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("")
def list_hooks(
    scope: Optional[str] = None,
    phase: Optional[str] = None,
    session: Session = Depends(get_session),
):
    stmt = select(HookDefinitionDB)
    if scope:
        stmt = stmt.where(HookDefinitionDB.scope == scope)
    if phase:
        stmt = stmt.where(HookDefinitionDB.phase == phase)
    items = session.exec(stmt).all()
    return [_hook_to_dict(h) for h in items]


@router.post("")
def create_hook(body: HookDefinitionCreate, session: Session = Depends(get_session)):
    hook = HookDefinitionDB(
        name=body.name,
        description=body.description,
        phase=body.phase,
        priority=body.priority,
        blocking=body.blocking,
        hook_class=body.hook_class,
        hook_config=json.dumps(body.hook_config) if body.hook_config else "{}",
        scope=body.scope,
        enabled=body.enabled,
        conditions=json.dumps(body.conditions) if body.conditions else "{}",
        tags=json.dumps(body.tags),
    )
    session.add(hook)
    session.commit()
    session.refresh(hook)
    return _hook_to_dict(hook)


@router.get("/{hook_id}")
def get_hook(hook_id: int, session: Session = Depends(get_session)):
    h = session.get(HookDefinitionDB, hook_id)
    if not h:
        raise HTTPException(status_code=404, detail="Hook not found")
    return _hook_to_dict(h)


@router.put("/{hook_id}")
def update_hook(
    hook_id: int, body: HookDefinitionUpdate, session: Session = Depends(get_session)
):
    h = session.get(HookDefinitionDB, hook_id)
    if not h:
        raise HTTPException(status_code=404, detail="Hook not found")

    update_data = body.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        if field_name in ("hook_config", "conditions", "tags") and value is not None:
            setattr(h, field_name, json.dumps(value))
        else:
            setattr(h, field_name, value)
    h.updated_at = datetime.utcnow()
    session.add(h)
    session.commit()
    session.refresh(h)
    return _hook_to_dict(h)


@router.delete("/{hook_id}")
def delete_hook(hook_id: int, session: Session = Depends(get_session)):
    h = session.get(HookDefinitionDB, hook_id)
    if not h:
        raise HTTPException(status_code=404, detail="Hook not found")
    session.delete(h)
    session.commit()
    return {"status": "deleted"}


@router.post("/{hook_id}/test")
def test_hook(hook_id: int, body: HookTestRequest, session: Session = Depends(get_session)):
    """Test a hook with mock context."""
    h = session.get(HookDefinitionDB, hook_id)
    if not h:
        raise HTTPException(status_code=404, detail="Hook not found")
    # TODO: actually instantiate and run the hook_class with the context
    return {
        "hook_id": hook_id,
        "hook_class": h.hook_class,
        "context": body.context,
        "result": {"status": "success", "message": "Hook test stub — implement HookEngine.run_phase() integration"},
    }
