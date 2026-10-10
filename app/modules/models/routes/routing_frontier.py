"""Model routing frontier routes (NEX-P4-003) — thin FastAPI layer.

All logic lives in
``common_lib.modules.orchestration.routing.{pareto,chains,canary,subagent,events}``.
This module only validates request shapes, enforces the canary flag gate
(404 while OFF — the route does not exist from the client's point of view),
and serializes service envelopes.

G1: thin routes only. G4: additive — mounted via ``router.include_router``.
G9: mutating canary ops refuse while
``orchestration.routing.canary.enabled`` is OFF; pure Pareto/chain/subagent
planning endpoints are ungated (no I/O, deterministic).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

frontier_router = APIRouter(prefix="/routing", tags=["Model Routing"])


class ParetoSignal(BaseModel):
    model_id: str
    workload: str = "chat"
    quality: float = 0.5
    cost_per_1k: float = 0.0
    success_rate: float = 1.0
    p50_ms: float = 500.0
    p95_ms: float = 1000.0
    error_rate: float = 0.0
    repair_effort: float = 0.0
    footprint_mb: float = 0.0
    locality: str = "local"
    capabilities: List[str] = Field(default_factory=list)


class ParetoQueryRequest(BaseModel):
    signals: List[ParetoSignal] = Field(default_factory=list)
    workload: str = "chat"
    constraints: Dict[str, Any] = Field(default_factory=dict)


class FallbackChainRequest(BaseModel):
    capability: str = "chat"
    ranked_model_ids: List[str] = Field(default_factory=list)
    candidates: Optional[List[Dict[str, Any]]] = None
    data_class: str = "public"


class FallbackResolveRequest(BaseModel):
    chain: Dict[str, Any] = Field(default_factory=dict)
    failed_model: str = ""
    data_class: str = "public"
    candidates: Optional[List[Dict[str, Any]]] = None
    cause: str = "model failure"


class CanaryStartRequest(BaseModel):
    workload: str = ""
    candidate_id: str = ""
    baseline_id: str = ""
    percent: float = 5.0
    guardrails: Dict[str, Any] = Field(default_factory=dict)


class CanaryRecordRequest(BaseModel):
    workload: str = ""
    metrics: Dict[str, Any] = Field(default_factory=dict)


class SubagentPlanRequest(BaseModel):
    task: str = ""
    risk_level: str = "R1"
    complexity: str = "low"
    data_class: str = "public"
    requested_workers: int = 3


_CANARY_FLAG = "orchestration.routing.canary.enabled"


def _require_canary() -> None:
    try:
        from common_lib.modules.orchestration.routing.flags import (
            is_enabled as _routing_enabled,
        )
    except ImportError:
        raise HTTPException(status_code=404, detail="Canary routing unavailable")
    if _routing_enabled(_CANARY_FLAG):
        return
    raise HTTPException(
        status_code=404,
        detail=(
            "Canary routing is gated behind the feature flag "
            f"'{_CANARY_FLAG}', which is currently OFF. Enable "
            "ROUTING_CANARY_ENABLED=true and restart."
        ),
    )


@frontier_router.post("/pareto")
async def pareto_query_endpoint(request: ParetoQueryRequest) -> Dict[str, Any]:
    """Per-workload Pareto frontier query (pure, ungated)."""
    try:
        from common_lib.modules.orchestration.routing.pareto import (
            ModelSignals,
            query_frontier,
        )

        signals = [ModelSignals(**s.model_dump()) for s in request.signals]
        return query_frontier(signals, request.workload, request.constraints)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pareto query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@frontier_router.post("/fallback-chain")
async def fallback_chain_endpoint(request: FallbackChainRequest) -> Dict[str, Any]:
    """Compatible fallback chain from a Pareto ranking (pure, ungated)."""
    try:
        from common_lib.modules.orchestration.routing.chains import (
            build_compatible_chain,
        )

        return build_compatible_chain(
            request.capability,
            list(request.ranked_model_ids),
            request.candidates,
            request.data_class,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fallback chain build failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@frontier_router.post("/fallback-resolve")
async def fallback_resolve_endpoint(request: FallbackResolveRequest) -> Dict[str, Any]:
    """Next eligible model after a failure (emits model.route.fallback)."""
    try:
        from common_lib.modules.orchestration.routing.chains import resolve_next

        return resolve_next(
            request.chain,
            request.failed_model,
            request.data_class,
            request.candidates,
            cause=request.cause,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fallback resolve failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@frontier_router.post("/subagent-plan")
async def subagent_plan_endpoint(request: SubagentPlanRequest) -> Dict[str, Any]:
    """Subagent role plan (pure, ungated)."""
    try:
        from common_lib.modules.orchestration.routing.subagent import (
            plan_subagent_routing,
        )

        return plan_subagent_routing(
            request.task,
            risk_level=request.risk_level,
            complexity=request.complexity,
            data_class=request.data_class,
            requested_workers=request.requested_workers,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Subagent plan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@frontier_router.post("/canary/start")
async def canary_start_endpoint(request: CanaryStartRequest) -> Dict[str, Any]:
    """Start a canary. 404 while the canary flag is OFF."""
    _require_canary()
    try:
        from common_lib.modules.orchestration.routing.canary import (
            CanaryService,
            Guardrails,
        )

        svc = CanaryService()
        guardrails = Guardrails(**request.guardrails) if request.guardrails else None
        return svc.start(
            request.workload,
            request.candidate_id,
            request.baseline_id,
            percent=request.percent,
            guardrails=guardrails,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Canary start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@frontier_router.post("/canary/record")
async def canary_record_endpoint(request: CanaryRecordRequest) -> Dict[str, Any]:
    """Record a canary observation (auto-rollback on breach). 404 when OFF."""
    _require_canary()
    try:
        from common_lib.modules.orchestration.routing.canary import CanaryService

        return CanaryService().record(request.workload, request.metrics)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Canary record failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@frontier_router.get("/canary/{workload}")
async def canary_status_endpoint(workload: str) -> Dict[str, Any]:
    """Canary status (diagnostic read, ungated)."""
    try:
        from common_lib.modules.orchestration.routing.canary import CanaryService

        return CanaryService().status(workload)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Canary status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@frontier_router.get("/events")
async def routing_events_endpoint(
    event_type: Optional[str] = None, limit: int = 50
) -> Dict[str, Any]:
    """Recent routing events (diagnostic read, ungated)."""
    try:
        from common_lib.modules.orchestration.routing.events import recent_events

        return {"events": recent_events(event_type, limit=limit)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Routing events read failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@frontier_router.get("/flags")
async def routing_flags_endpoint() -> Dict[str, Any]:
    """Routing feature-flag state (diagnostic read, ungated)."""
    try:
        from common_lib.modules.orchestration.routing.flags import describe_flags

        return {"flags": describe_flags()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Routing flags read failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
