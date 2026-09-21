"""Capability registry + model certification — thin router (COGR Phase 4.1).

All logic lives in common_lib.modules.ai_models.registry.*.
Endpoints (mounted under /api/v1/ai_models):
- POST /ai_models/capabilities          → register a capability
- GET  /ai_models/capabilities          → list registered capabilities
- POST /ai_models/models/register       → run discovery flow for a model
- POST /ai_models/models/{id}/certify   → lifecycle transition
- GET  /ai_models/models/{id}/eligibility → production eligibility
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()

_CAPABILITIES: Dict[str, Dict[str, Any]] = {}


@router.post("/capabilities")
async def capabilities_register(body: Dict[str, Any]) -> Dict[str, Any]:
    """Register a capability (no business logic — validates via common_lib model)."""
    try:
        from common_lib.modules.ai_models.registry.capability import Capability

        cap = Capability(**body)
        _CAPABILITIES[cap.id] = cap.model_dump()
        return {"capability": _CAPABILITIES[cap.id]}
    except Exception as exc:  # noqa: BLE001
        logger.error("capabilities.register failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/capabilities")
async def capabilities_list() -> Dict[str, Any]:
    """List registered capabilities."""
    return {"capabilities": list(_CAPABILITIES.values())}


@router.post("/models/register")
async def models_register(body: Dict[str, Any]) -> Dict[str, Any]:
    """Run the discovery flow for a model (delegates to common_lib)."""
    try:
        from common_lib.modules.ai_models.registry.discovery import discover

        return dict(discover(dict(body)))
    except Exception as exc:  # noqa: BLE001
        logger.error("models.register failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/models/{model_id}/certify")
async def models_certify(
    model_id: str, body: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Record a lifecycle transition for a model."""
    try:
        from common_lib.modules.ai_models.registry.certification import (
            ModelLifecycleState,
            certify,
        )

        state = ModelLifecycleState(str((body or {}).get("state", "available")))
        new_state = certify(model_id, state)
        return {"model_id": model_id, "state": str(new_state.value)}
    except Exception as exc:  # noqa: BLE001
        logger.error("models.certify failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/models/{model_id}/eligibility")
async def models_eligibility(model_id: str) -> Dict[str, Any]:
    """Check production eligibility for a model."""
    try:
        from common_lib.modules.ai_models.registry.certification import (
            is_production_eligible,
            lifecycle_state_of,
        )

        state = lifecycle_state_of(model_id)
        return {
            "model_id": model_id,
            "state": str(state.value),
            "production_eligible": bool(is_production_eligible(model_id)),
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("models.eligibility failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
