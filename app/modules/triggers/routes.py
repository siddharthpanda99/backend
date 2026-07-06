"""
Unified Triggers Router

Thin FastAPI router for the unified trigger system.
All CRUD + fire/state-transition endpoints.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.triggers.models import TriggerDB
from common_lib.modules.triggers.types import TriggerType, TriggerState
from common_lib.modules.triggers.manager import get_trigger_manager
from common_lib.modules.triggers.definition import Trigger

router = APIRouter(prefix="/triggers", tags=["Unified Triggers"])


# ── Pydantic Schemas ────────────────────────────────────────────────


class TriggerCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: str = "event"
    event_config: Optional[Dict[str, Any]] = None
    time_config: Optional[Dict[str, Any]] = None
    condition_config: Optional[Dict[str, Any]] = None
    webhook_config: Optional[Dict[str, Any]] = None
    composite_config: Optional[Dict[str, Any]] = None
    enabled: bool = True
    schedule_expression: Optional[str] = None
    schedule_timezone: Optional[str] = None
    target_type: str = "workflow"
    target_id: Optional[str] = None
    scope: str = "universal"
    priority: int = 100
    tags: list[str] = []
    cooldown_seconds: int = 0
    max_fires: Optional[int] = None


class TriggerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    event_config: Optional[Dict[str, Any]] = None
    time_config: Optional[Dict[str, Any]] = None
    condition_config: Optional[Dict[str, Any]] = None
    webhook_config: Optional[Dict[str, Any]] = None
    composite_config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    schedule_expression: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    scope: Optional[str] = None
    priority: Optional[int] = None
    tags: Optional[list[str]] = None
    cooldown_seconds: Optional[int] = None
    max_fires: Optional[int] = None


class StateTransition(BaseModel):
    state: str
    reason: Optional[str] = ""


# ── Serialiser ──────────────────────────────────────────────────────


def _trigger_to_dict(t: TriggerDB) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "trigger_type": t.trigger_type,
        "event_config": json.loads(t.event_config) if t.event_config else {},
        "time_config": json.loads(t.time_config) if t.time_config else {},
        "condition_config": json.loads(t.condition_config) if t.condition_config else {},
        "webhook_config": json.loads(t.webhook_config) if t.webhook_config else {},
        "composite_config": json.loads(t.composite_config) if t.composite_config else {},
        "state": t.state,
        "enabled": t.enabled,
        "schedule_expression": t.schedule_expression,
        "schedule_timezone": t.schedule_timezone,
        "target_type": t.target_type,
        "target_id": t.target_id,
        "scope": t.scope,
        "priority": t.priority,
        "tags": json.loads(t.tags) if t.tags else [],
        "cooldown_seconds": t.cooldown_seconds,
        "max_fires": t.max_fires,
        "fire_count": t.fire_count,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "last_fired_at": t.last_fired_at.isoformat() if t.last_fired_at else None,
        "next_fire_at": t.next_fire_at.isoformat() if t.next_fire_at else None,
        "metadata_json": json.loads(t.metadata_json) if t.metadata_json else {},
    }


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("")
def list_triggers(
    scope: Optional[str] = None,
    trigger_type: Optional[str] = None,
    state: Optional[str] = None,
    session: Session = Depends(get_session),
):
    stmt = select(TriggerDB)
    if scope:
        stmt = stmt.where(TriggerDB.scope == scope)
    if trigger_type:
        stmt = stmt.where(TriggerDB.trigger_type == trigger_type)
    if state:
        stmt = stmt.where(TriggerDB.state == state)
    items = session.exec(stmt).all()
    return [_trigger_to_dict(t) for t in items]


@router.post("")
def create_trigger(body: TriggerCreate, session: Session = Depends(get_session)):
    trigger = TriggerDB(
        name=body.name,
        description=body.description,
        trigger_type=body.trigger_type,
        event_config=json.dumps(body.event_config) if body.event_config else "{}",
        time_config=json.dumps(body.time_config) if body.time_config else "{}",
        condition_config=json.dumps(body.condition_config) if body.condition_config else "{}",
        webhook_config=json.dumps(body.webhook_config) if body.webhook_config else "{}",
        composite_config=json.dumps(body.composite_config) if body.composite_config else "{}",
        enabled=body.enabled,
        state="draft",
        schedule_expression=body.schedule_expression,
        schedule_timezone=body.schedule_timezone,
        target_type=body.target_type,
        target_id=body.target_id,
        scope=body.scope,
        priority=body.priority,
        tags=json.dumps(body.tags),
        cooldown_seconds=body.cooldown_seconds,
        max_fires=body.max_fires,
    )
    session.add(trigger)
    session.commit()
    session.refresh(trigger)

    # Also register in-memory
    mgr = get_trigger_manager()
    db_trigger = Trigger.from_db(trigger)
    mgr.register(db_trigger)

    return _trigger_to_dict(trigger)


@router.get("/{trigger_id}")
def get_trigger(trigger_id: int, session: Session = Depends(get_session)):
    t = session.get(TriggerDB, trigger_id)
    if not t:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return _trigger_to_dict(t)


@router.put("/{trigger_id}")
def update_trigger(
    trigger_id: int, body: TriggerUpdate, session: Session = Depends(get_session)
):
    t = session.get(TriggerDB, trigger_id)
    if not t:
        raise HTTPException(status_code=404, detail="Trigger not found")

    update_data = body.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        if field_name in ("event_config", "time_config", "condition_config", "webhook_config", "composite_config", "tags") and value is not None:
            setattr(t, field_name, json.dumps(value))
        else:
            setattr(t, field_name, value)
    t.updated_at = datetime.utcnow()
    session.add(t)
    session.commit()
    session.refresh(t)
    return _trigger_to_dict(t)


@router.delete("/{trigger_id}")
def delete_trigger(trigger_id: int, session: Session = Depends(get_session)):
    t = session.get(TriggerDB, trigger_id)
    if not t:
        raise HTTPException(status_code=404, detail="Trigger not found")
    session.delete(t)
    session.commit()
    # Unregister from in-memory
    mgr = get_trigger_manager()
    mgr.unregister(str(trigger_id))
    return {"status": "deleted"}


@router.post("/{trigger_id}/fire")
def fire_trigger(trigger_id: int, session: Session = Depends(get_session)):
    t = session.get(TriggerDB, trigger_id)
    if not t:
        raise HTTPException(status_code=404, detail="Trigger not found")
    if not t.enabled:
        raise HTTPException(status_code=400, detail="Trigger is disabled")
    # Update fire count
    t.fire_count += 1
    t.last_fired_at = datetime.utcnow()
    session.add(t)
    session.commit()
    # Fire via in-memory manager
    mgr = get_trigger_manager()
    result = mgr.fire(str(trigger_id))
    result["fire_count"] = t.fire_count
    return result


@router.put("/{trigger_id}/state")
def transition_state(
    trigger_id: int, body: StateTransition, session: Session = Depends(get_session)
):
    t = session.get(TriggerDB, trigger_id)
    if not t:
        raise HTTPException(status_code=404, detail="Trigger not found")

    valid_states = {s.value for s in TriggerState}
    if body.state not in valid_states:
        raise HTTPException(status_code=400, detail=f"Invalid state: {body.state}")

    t.state = body.state
    t.enabled = body.state == "active"
    t.updated_at = datetime.utcnow()
    session.add(t)
    session.commit()
    session.refresh(t)
    return _trigger_to_dict(t)
