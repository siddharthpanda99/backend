"""Cognitive Runtime execute routes — thin router layer."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.cognitive_runtime.models.constraints import ExecutionConstraints
from app.modules.cognitive_runtime.routes._runtime import get_runtime

router = APIRouter(prefix="/execute", tags=["Cognitive Execute"])
_runtime = get_runtime()


class ExecuteRequest(BaseModel):
    plan: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)


class LoopRequest(BaseModel):
    task: str = Field(min_length=1)
    mode: str = Field(default="EXECUTE")
    max_iterations: int = Field(default=5, ge=1, le=20)


@router.post("")
async def execute(request: ExecuteRequest):
    """Execute an ExecutionPlan DAG."""
    try:
        record = await _runtime.execute(
            request.plan,
            request.context,
            ExecutionConstraints(**request.constraints),
        )
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execute failed: {e}")


@router.post("/loop")
async def run_loop(request: LoopRequest):
    """Run the autonomous agent loop (DRY_RUN/SIMULATE/PLAN_ONLY/EXECUTE)."""
    try:
        from common_lib.modules.cognitive_runtime.services.agent_loop import AgentLoop

        loop = AgentLoop(_runtime)
        record = await loop.run(
            request.task, mode=request.mode, max_iterations=request.max_iterations
        )
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loop failed: {e}")
