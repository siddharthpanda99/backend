"""Cognitive Runtime plan routes — thin router layer."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.modules.cognitive_runtime.routes._runtime import get_runtime

router = APIRouter(prefix="/plan", tags=["Cognitive Plan"])
_runtime = get_runtime()


class PlanRequest(BaseModel):
    task: str = Field(min_length=1)
    capabilities: list[str] | None = Field(default=None)


class PipelineRunRequest(BaseModel):
    spec: dict = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)


@router.post("")
async def build_plan(request: PlanRequest):
    """Build an ExecutionPlan DAG for a task."""
    try:
        plan = await _runtime.plan(request.task, request.capabilities)
        return plan.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plan failed: {e}")


@router.post("/pipeline")
async def run_pipeline(request: PipelineRunRequest):
    """Parse, validate, and run a pipeline DSL spec."""
    try:
        from common_lib.modules.cognitive_runtime.pipelines.runner import run_pipeline

        record = await run_pipeline(request.spec, request.context)
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline run failed: {e}")
