"""Orchestration API router.

Pattern follows ``workflows/routes/index.py`` (thin router delegating to
common_lib services). All endpoints live under ``/api/v1/orchestration/``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from common_lib.modules.orchestration.agents.multi_agent import (
    MultiAgentCoordinator,
    PlannerAgent,
    ExecutorAgent,
    CriticAgent,
    AgentTask,
)
from common_lib.modules.orchestration.routing.role_router import (
    RoleRouter,
)
from common_lib.modules.orchestration.agents import GradingJudge

logger = logging.getLogger(__name__)

router = APIRouter()


# =========================================================================
# Request / Response schemas
# =========================================================================


class CoordinateRequest(BaseModel):
    user_request: str
    available_agents: List[str] = ["planner", "executor", "critic"]
    use_critic: bool = True
    context: Optional[Dict[str, Any]] = None


class TaskResponse(BaseModel):
    task_id: str
    description: str
    agent_role: str
    status: str
    result: Optional[Any] = None
    grade: Optional[str] = None


class CoordinateResponse(BaseModel):
    coordination_id: str
    status: str
    tasks: List[TaskResponse]
    duration_ms: int
    needs_revision: bool = False
    feedback: Optional[str] = None


class RouteRequest(BaseModel):
    task_description: str
    prefer_local: bool = False
    min_quality: Optional[str] = None


class RouteResponse(BaseModel):
    role: str
    confidence: float
    model: Optional[Dict[str, Any]] = None
    fallback_model: Optional[Dict[str, Any]] = None
    explanation: str
    matched_patterns: List[str] = []


# =========================================================================
# ── Multi-Agent Coordination ─────────────────────────────────────────
# =========================================================================


@router.post("/agents/coordinate", response_model=CoordinateResponse)
async def coordinate_agents(req: CoordinateRequest) -> Dict[str, Any]:
    """Execute a task through multi-agent coordination.

    Flow: Planner decomposes → Executor runs each subtask → Critic reviews.
    Supports optional GradingJudge for A–F evaluation of each task result.
    """
    try:
        gradient_judge = GradingJudge()

        planner = PlannerAgent()
        executor = ExecutorAgent()
        critic = CriticAgent(grading_judge=gradient_judge)

        coordinator = MultiAgentCoordinator(
            planner=planner,
            executor=executor,
            critic=critic,
        )

        result = await coordinator.execute(
            user_request=req.user_request,
            available_agents=req.available_agents,
            context=req.context or {},
            use_critic=req.use_critic,
        )

        tasks = []
        for task in result.tasks:
            grade = None
            if task.result and isinstance(task.result, dict):
                grade = task.result.get("grade")
            tasks.append(
                TaskResponse(
                    task_id=task.task_id or str(uuid.uuid4()),
                    description=task.description,
                    agent_role=task.agent_role,
                    status=task.status,
                    result=task.result,
                    grade=grade,
                )
            )

        needs_revision = False
        feedback = None
        if result.final_result:
            needs_revision = result.final_result.get("needs_revision", False)
            feedback = result.final_result.get("feedback")

        return {
            "coordination_id": result.coordination_id,
            "status": result.status,
            "tasks": [t.model_dump() for t in tasks],
            "duration_ms": result.duration_ms,
            "needs_revision": needs_revision,
            "feedback": feedback,
        }

    except Exception as exc:
        logger.error("Coordination failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# =========================================================================
# ── Role Routing ─────────────────────────────────────────────────────
# =========================================================================


@router.post("/routing/route", response_model=RouteResponse)
async def route_task(req: RouteRequest) -> Dict[str, Any]:
    """Classify a task description into a role and select the best-fit model.

    Uses pattern-based classification (no LLM call) to assign
    Explore/Plan/Build/Review roles with confidence scoring.
    """
    try:
        router_ = RoleRouter()
        result = router_.route(
            task_description=req.task_description,
            prefer_local=req.prefer_local,
            min_quality=req.min_quality,
        )

        return {
            "role": result.role.value
            if hasattr(result.role, "value")
            else str(result.role),
            "confidence": result.confidence,
            "model": {
                "id": result.model.id,
                "name": result.model.name,
                "provider": result.model.provider,
                "quality": result.model.metadata.get("quality", "good")
                if result.model.metadata
                else "good",
            }
            if result.model
            else None,
            "fallback_model": {
                "id": result.fallback_model.id,
                "name": result.fallback_model.name,
            }
            if result.fallback_model
            else None,
            "explanation": result.explanation,
        }

    except Exception as exc:
        logger.error("Routing failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# =========================================================================
# ── Single Scorer (NEX-P4-002) ─────────────────────────────────────────
# =========================================================================


class ScorerResolveRequest(BaseModel):
    capability: str
    candidates: Optional[List[Dict[str, Any]]] = None
    workload: Optional[str] = None
    data_class: str = "public"
    constraints: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    availability: Optional[Dict[str, bool]] = None
    capacity: Optional[Dict[str, Any]] = None
    use_live_sources: bool = True


class ScorerFeedbackRequest(BaseModel):
    model_id: str
    capability: str
    success: bool
    latency_ms: Optional[float] = None
    cost: Optional[float] = None
    error: Optional[str] = None


@router.post("/routing/resolve")
async def resolve_model_route(req: ScorerResolveRequest) -> Dict[str, Any]:
    """Run the single routing scorer (NEX-P4-002).

    Thin wrapper over ``orchestration.routing.scorer.resolve_route``:
    ordered pipeline (policy → privacy → capability → quality floor →
    availability/capacity → Pareto rank → score) with a per-stage decision
    log. Flag-off the scorer flag falls back to the legacy COGR route.
    """
    try:
        from common_lib.modules.orchestration.routing import flags as routing_flags
        from common_lib.modules.orchestration.routing import scorer as routing_scorer

        if not routing_flags.scorer_enabled():
            from common_lib.modules.orchestration.routing.decision_function import (
                route as legacy_route,
            )

            legacy = legacy_route(
                req.capability,
                {"candidates": req.candidates or []},
                dict(req.constraints or {}),
            )
            return {
                "capability": legacy.capability,
                "selected_id": legacy.selected.id if legacy.selected else None,
                "runner_up_id": legacy.runner_up.id if legacy.runner_up else None,
                "scores": dict(legacy.scores),
                "pareto_ranks": {},
                "trace": [],
                "reasons": list(legacy.reasons),
                "denied": legacy.denied,
                "denial_reason": "" if not legacy.denied else "; ".join(legacy.reasons),
                "via": "legacy",
            }
        decision = routing_scorer.resolve_route(
            capability=req.capability,
            candidates=req.candidates,
            workload=req.workload,
            data_class=req.data_class,
            constraints=req.constraints,
            context=req.context,
            availability=req.availability,
            capacity=req.capacity,
            use_live_sources=req.use_live_sources,
        )
        decision["via"] = "scorer"
        return decision
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Scorer resolve failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/routing/feedback")
async def record_route_feedback(req: ScorerFeedbackRequest) -> Dict[str, Any]:
    """Record a routing outcome for future quality priors (NEX-P4-002)."""
    try:
        from common_lib.modules.orchestration.routing import scorer as routing_scorer

        return routing_scorer.record_feedback(
            model_id=req.model_id,
            capability=req.capability,
            success=req.success,
            latency_ms=req.latency_ms,
            cost=req.cost,
            error=req.error,
        )
    except Exception as exc:
        logger.error("Scorer feedback failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# =========================================================================
# ── Health / Status ─────────────────────────────────────────────────
# =========================================================================


@router.get("/status")
async def orchestration_status() -> Dict[str, Any]:
    """Get orchestration system status overview."""
    return {
        "status": "operational",
        "agents": {
            "planner": True,
            "executor": True,
            "critic": True,
            "grading_judge": True,
        },
        "roles": ["explore", "plan", "build", "review"],
        "version": "1.0.0",
    }


from app.modules.orchestration.session_runtime_routes import (
    router as session_runtime_router,
)

router.include_router(session_runtime_router)

try:  # COGR cognitive routing (additive; never touches existing routes)
    from app.modules.orchestration.cognitive_routing import (
        router as cognitive_routing_router,
    )

    router.include_router(cognitive_routing_router)
except Exception:  # noqa: BLE001
    pass

__all__ = ["router"]
