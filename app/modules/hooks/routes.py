"""
Unified Hooks Router

Thin FastAPI router for the unified hook definition system.
All CRUD + test endpoints.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.integration.ports.interceptors.triggers_port import (
    get_trigger_models_module,
)

router = APIRouter(prefix="/hook-definitions", tags=["Unified Hooks"])

# G9/G4 — actually executing a stored hook definition against a mock context
# is new behaviour, so it ships behind a default-OFF flag. Until it exists,
# the endpoint answers 501 rather than the "success" it used to claim.
_TEST_EXECUTION_ENABLED = os.getenv(
    "HOOKS_ENABLE_HOOK_TEST_EXECUTION", ""
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _hook_definition_model():
    """Resolve ``HookDefinitionDB`` through the integration port (G2).

    This module previously imported ``common_lib.modules.triggers.models``
    directly. That is a cross-module import outside ``integration/ports/``,
    and the cross-module import guard does not scan ``Backend/app`` — which
    is why it reported zero violations while this line existed. The hooks
    engine already reached the same model through
    ``interceptors.triggers_port.get_trigger_models_module``; this now uses
    the same door, so there is one resolution path rather than two that can
    drift.
    """
    models_module = get_trigger_models_module()
    if models_module is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Hook definitions are unavailable: the triggers models module "
                "could not be resolved through the integration port."
            ),
        )
    return models_module.HookDefinitionDB


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
def test_hook(
    hook_id: int, body: HookTestRequest, session: Session = Depends(get_session)
):
    """Test a hook with mock context.

    This endpoint reported ``result.status == "success"`` for a test that had
    not run: the body was a literal dict with a ``# TODO`` above it and no
    hook was ever instantiated or executed. A caller polling this endpoint to
    confirm a hook works was told it worked. 501 is the truthful answer until
    the execution is actually wired to ``HookEngine.run_phase``.

    G9/G4 — the real implementation is new behaviour, so it is gated behind
    ``HOOKS_ENABLE_HOOK_TEST_EXECUTION`` (default OFF) rather than
    implemented speculatively.
    """
    HookDefinitionDB = _hook_definition_model()
    h = session.get(HookDefinitionDB, hook_id)
    if not h:
        raise HTTPException(status_code=404, detail="Hook not found")

    if not _TEST_EXECUTION_ENABLED:
        raise HTTPException(
            status_code=501,
            detail=(
                "Hook test execution is not implemented. This endpoint no "
                "longer reports a 'success' result for a test that did not "
                "run. To exercise a hook for real, register it and call "
                f"POST /api/v1/hooks/{{hook_id}}/trigger — or set "
                "HOOKS_ENABLE_HOOK_TEST_EXECUTION=true once the HookEngine "
                "integration lands."
            ),
        )

    raise HTTPException(
        status_code=501,
        detail="Hook test execution is gated but not yet implemented.",
    )
