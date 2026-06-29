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
            tasks.append(TaskResponse(
                task_id=task.task_id or str(uuid.uuid4()),
                description=task.description,
                agent_role=task.agent_role,
                status=task.status,
                result=task.result,
                grade=grade,
            ))

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
            "role": result.role.value if hasattr(result.role, 'value') else str(result.role),
            "confidence": result.confidence,
            "model": {
                "id": result.model.id,
                "name": result.model.name,
                "provider": result.model.provider,
                "quality": result.model.metadata.get("quality", "good") if result.model.metadata else "good",
            } if result.model else None,
            "fallback_model": {
                "id": result.fallback_model.id,
                "name": result.fallback_model.name,
            } if result.fallback_model else None,
            "explanation": result.explanation,
        }

    except Exception as exc:
        logger.error("Routing failed: %s", exc, exc_info=True)
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


__all__ = ["router"]
