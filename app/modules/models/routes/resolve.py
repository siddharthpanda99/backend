"""Model resolve router — thin HTTP adapter for NEX-P4-001 (G1).

All logic lives in ``common_lib.modules.ai_models.routing``; this module
only maps the HTTP call onto ``resolve_models`` and serialises the result.

- ``POST /api/v1/models/resolve`` → eligible set + chosen + reasons for a
  workload + constraints pair (SSOT §10.3 taxonomy, §10.4 steps 1–2).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class ResolveRequest(BaseModel):
    """Resolve input: workload key plus optional routing constraints."""

    workload: str = Field(..., description="SSOT §10.3 workload key")
    constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional constraints: max_cost_per_1k, max_latency_p95_ms, "
            "min_quality, required_ops, allowed_providers, confidential, "
            "allow_hosted_for_confidential, est_tokens_in/out"
        ),
    )


class ResolveResponse(BaseModel):
    """Resolve output: eligible set + chosen + reasons."""

    ok: bool = True
    workload: Optional[str] = None
    eligible: List[Dict[str, Any]] = Field(default_factory=list)
    eligible_count: int = 0
    excluded: Dict[str, List[str]] = Field(default_factory=dict)
    chosen: Optional[Dict[str, Any]] = None
    reasons: List[str] = Field(default_factory=list)
    disabled: Optional[bool] = None
    status: Optional[str] = None
    flag: Optional[str] = None
    reason: Optional[str] = None
    error: Optional[str] = None
    workload_keys: Optional[List[str]] = None


def _model_dicts() -> List[Dict[str, Any]]:
    from common_lib.modules.ai_models.container import AIModelsContainer

    container = AIModelsContainer()
    try:
        container.health_monitor.verify_all_models()
    except Exception as exc:  # noqa: BLE001
        logger.warning("models.resolve health check best-effort failed: %s", exc)
    try:
        models = container.registry_service.list_models()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))
    out: List[Dict[str, Any]] = []
    for m in models:
        try:
            out.append(m.model_dump())
        except Exception:  # noqa: BLE001
            out.append(dict(m))
    return out


@router.post("/resolve", response_model=ResolveResponse)
async def resolve_model(payload: ResolveRequest) -> Dict[str, Any]:
    """Choose the eligible model/deployment for a workload (SSOT §10.4)."""
    from common_lib.modules.ai_models.routing.resolve import resolve_models

    try:
        result = resolve_models(
            payload.workload,
            payload.constraints,
            candidates=_model_dicts(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("models.resolve failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    if result.get("ok") is False and result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result
