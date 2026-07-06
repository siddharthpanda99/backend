"""
Unified Interceptors Router

Thin FastAPI router for the unified interceptor definition system.
CRUD endpoints for interceptors that pre-process events before rules.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.triggers.models import InterceptorDefinitionDB

router = APIRouter(prefix="/interceptors", tags=["Unified Interceptors"])


# ── Pydantic Schemas ────────────────────────────────────────────────


class InterceptorCreate(BaseModel):
    name: str
    description: Optional[str] = None
    priority: int = 100
    policy_id: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    action: str = "chain"
    enabled: bool = True
    scope: str = "universal"
    triggers_data: Optional[Dict[str, Any]] = None
    hooks_data: Optional[Dict[str, Any]] = None
    approvers: Optional[Dict[str, Any]] = None
    timeout: Optional[Dict[str, Any]] = None
    escalation: Optional[Dict[str, Any]] = None


class InterceptorUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    policy_id: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    action: Optional[str] = None
    enabled: Optional[bool] = None
    scope: Optional[str] = None
    triggers_data: Optional[Dict[str, Any]] = None
    hooks_data: Optional[Dict[str, Any]] = None
    approvers: Optional[Dict[str, Any]] = None
    timeout: Optional[Dict[str, Any]] = None
    escalation: Optional[Dict[str, Any]] = None


# ── Serialiser ──────────────────────────────────────────────────────


def _interceptor_to_dict(i: InterceptorDefinitionDB) -> dict:
    return {
        "id": i.id,
        "name": i.name,
        "description": i.description,
        "priority": i.priority,
        "policy_id": i.policy_id,
        "conditions": json.loads(i.conditions) if i.conditions else [],
        "action": i.action,
        "enabled": i.enabled,
        "scope": i.scope,
        "triggers_data": json.loads(i.triggers_data) if i.triggers_data else [],
        "hooks_data": json.loads(i.hooks_data) if i.hooks_data else [],
        "approvers": json.loads(i.approvers) if i.approvers else {},
        "timeout": json.loads(i.timeout) if i.timeout else {},
        "escalation": json.loads(i.escalation) if i.escalation else {},
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("")
def list_interceptors(
    scope: Optional[str] = None,
    action: Optional[str] = None,
    session: Session = Depends(get_session),
):
    stmt = select(InterceptorDefinitionDB)
    if scope:
        stmt = stmt.where(InterceptorDefinitionDB.scope == scope)
    if action:
        stmt = stmt.where(InterceptorDefinitionDB.action == action)
    items = session.exec(stmt).all()
    return [_interceptor_to_dict(i) for i in items]


@router.post("")
def create_interceptor(body: InterceptorCreate, session: Session = Depends(get_session)):
    interceptor = InterceptorDefinitionDB(
        name=body.name,
        description=body.description,
        priority=body.priority,
        policy_id=body.policy_id,
        conditions=json.dumps(body.conditions) if body.conditions else "[]",
        action=body.action,
        enabled=body.enabled,
        scope=body.scope,
        triggers_data=json.dumps(body.triggers_data) if body.triggers_data else "[]",
        hooks_data=json.dumps(body.hooks_data) if body.hooks_data else "[]",
        approvers=json.dumps(body.approvers) if body.approvers else "{}",
        timeout=json.dumps(body.timeout) if body.timeout else "{}",
        escalation=json.dumps(body.escalation) if body.escalation else "{}",
    )
    session.add(interceptor)
    session.commit()
    session.refresh(interceptor)
    return _interceptor_to_dict(interceptor)


@router.get("/{interceptor_id}")
def get_interceptor(interceptor_id: int, session: Session = Depends(get_session)):
    i = session.get(InterceptorDefinitionDB, interceptor_id)
    if not i:
        raise HTTPException(status_code=404, detail="Interceptor not found")
    return _interceptor_to_dict(i)


@router.put("/{interceptor_id}")
def update_interceptor(
    interceptor_id: int, body: InterceptorUpdate, session: Session = Depends(get_session)
):
    i = session.get(InterceptorDefinitionDB, interceptor_id)
    if not i:
        raise HTTPException(status_code=404, detail="Interceptor not found")

    update_data = body.model_dump(exclude_unset=True)
    json_fields = ("conditions", "triggers_data", "hooks_data", "approvers", "timeout", "escalation")
    for field_name, value in update_data.items():
        if field_name in json_fields and value is not None:
            setattr(i, field_name, json.dumps(value))
        else:
            setattr(i, field_name, value)
    i.updated_at = datetime.utcnow()
    session.add(i)
    session.commit()
    session.refresh(i)
    return _interceptor_to_dict(i)


@router.delete("/{interceptor_id}")
def delete_interceptor(interceptor_id: int, session: Session = Depends(get_session)):
    i = session.get(InterceptorDefinitionDB, interceptor_id)
    if not i:
        raise HTTPException(status_code=404, detail="Interceptor not found")
    session.delete(i)
    session.commit()
    return {"status": "deleted"}
