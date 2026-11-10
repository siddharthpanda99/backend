"""Effects API Router — Thin Transport Layer

Routes delegate to common_lib.modules.effects.service.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.effects.schemas import (
    EffectCreate,
    EffectRead,
    EffectHealthRead,
    EffectRetryRequest,
    EffectCancelRequest,
    EffectsDrainRequest,
)
from common_lib.modules.effects.service import get_effects_service
from common_lib.modules.effects.exceptions import (
    EffectsError,
    EffectNotFoundError,
    EffectHandlerNotFoundError,
    InvalidEffectError,
)

router = APIRouter(prefix="/effects", tags=["effects"])


@router.post("", response_model=EffectRead, status_code=201)
def enqueue_effect(payload: EffectCreate) -> EffectRead:
    """Enqueue a new effect work item."""
    try:
        svc = get_effects_service()
        row = svc.enqueue(kind=payload.kind, key=payload.key, payload=payload.payload)
        return EffectRead.model_validate(row)
    except EffectHandlerNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except EffectsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/{effect_id}", response_model=EffectRead)
def get_effect(effect_id: UUID) -> EffectRead:
    """Get an effect by ID."""
    svc = get_effects_service()
    row = svc.get(effect_id)
    if not row:
        raise HTTPException(status_code=404, detail="Effect not found")
    return EffectRead.model_validate(row)


@router.get("", response_model=list[EffectRead])
def list_effects(
    status: str | None = Query(None, description="Filter by status"),
    kind: str | None = Query(None, description="Filter by kind"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[EffectRead]:
    """List effects with optional filters."""
    svc = get_effects_service()
    rows = svc.list(status=status, kind=kind, limit=limit, offset=offset)
    return [EffectRead.model_validate(r) for r in rows]


@router.get("/health", response_model=dict[str, EffectHealthRead])
def get_health() -> dict[str, EffectHealthRead]:
    """Get health status for all effect kinds."""
    svc = get_effects_service()
    health = svc.health()
    return {k: EffectHealthRead.model_validate(v) for k, v in health.items()}


@router.post("/{effect_id}/retry", response_model=EffectRead)
def retry_effect(effect_id: UUID, _: EffectRetryRequest) -> EffectRead:
    """Retry a failed effect."""
    try:
        svc = get_effects_service()
        row = svc.retry(effect_id)
        return EffectRead.model_validate(row)
    except EffectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidEffectError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{effect_id}/cancel", response_model=EffectRead)
def cancel_effect(effect_id: UUID, _: EffectCancelRequest) -> EffectRead:
    """Cancel a pending/running effect."""
    try:
        svc = get_effects_service()
        row = svc.cancel(effect_id)
        return EffectRead.model_validate(row)
    except EffectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidEffectError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/drain", response_model=dict[str, bool])
def drain_effects(_: EffectsDrainRequest) -> dict[str, bool]:
    """Drain the effects processor (graceful shutdown)."""
    svc = get_effects_service()
    svc.drain()
    return {"drained": True}
