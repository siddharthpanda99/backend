"""Cognitive Runtime MCP Tools.

Exposes infer/decide/plan/execute/run_pipeline/loop through MCP.
Thin transport: all logic lives in common_lib.modules.cognitive_runtime.
"""

from typing import Any

from pydantic import BaseModel, Field


class InferRequest(BaseModel):
    capability: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)


class DecideRequest(BaseModel):
    decision_type: str = "ROUTING"
    context: dict[str, Any] = Field(default_factory=dict)
    question: str = ""
    options: list[dict[str, Any]] = Field(default_factory=list)


class PlanRequest(BaseModel):
    task: str = Field(min_length=1)
    capabilities: list[str] | None = None


class ExecuteRequest(BaseModel):
    plan: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)


class PipelineRequest(BaseModel):
    spec: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class LoopRequest(BaseModel):
    task: str = Field(min_length=1)
    mode: str = "EXECUTE"
    max_iterations: int = 5


def _get_runtime():
    from common_lib.modules.cognitive_runtime.services.runtime import CognitiveRuntime

    return CognitiveRuntime()


async def cognitive_infer(request: InferRequest) -> dict:
    """Run a single capability inference with budgeted context."""
    import asyncio

    from common_lib.modules.cognitive_runtime.models.constraints import (
        ExecutionConstraints,
    )
    from common_lib.modules.cognitive_runtime.models.context import CognitiveContext

    try:
        result = asyncio.run(
            _get_runtime().infer(
                request.capability,
                CognitiveContext(**request.context),
                ExecutionConstraints(**request.constraints),
            )
        )
        return result.model_dump()
    except Exception as e:
        raise Exception(f"Cognitive infer failed: {e}")


async def cognitive_decide(request: DecideRequest) -> dict:
    """Make a routed decision via NEXUS (with safe fallback)."""
    import asyncio

    from common_lib.modules.cognitive_runtime.models.context import CognitiveContext

    try:
        result = asyncio.run(
            _get_runtime().decide(
                request.decision_type,
                CognitiveContext(**request.context),
                request.question,
                request.options,
            )
        )
        return result.model_dump()
    except Exception as e:
        raise Exception(f"Cognitive decide failed: {e}")


async def cognitive_plan(request: PlanRequest) -> dict:
    """Build an ExecutionPlan DAG for a task."""
    import asyncio

    try:
        plan = asyncio.run(_get_runtime().plan(request.task, request.capabilities))
        return plan.model_dump()
    except Exception as e:
        raise Exception(f"Cognitive plan failed: {e}")


async def cognitive_execute(request: ExecuteRequest) -> dict:
    """Execute an ExecutionPlan DAG with budget enforcement."""
    import asyncio

    from common_lib.modules.cognitive_runtime.models.constraints import (
        ExecutionConstraints,
    )

    try:
        record = asyncio.run(
            _get_runtime().execute(
                request.plan,
                request.context,
                ExecutionConstraints(**request.constraints),
            )
        )
        return record
    except Exception as e:
        raise Exception(f"Cognitive execute failed: {e}")


async def cognitive_run_pipeline(request: PipelineRequest) -> dict:
    """Parse, validate, and run a pipeline DSL spec."""
    import asyncio

    try:
        from common_lib.modules.cognitive_runtime.pipelines.runner import (
            run_pipeline as _run,
        )

        return asyncio.run(_run(request.spec, request.context))
    except Exception as e:
        raise Exception(f"Cognitive pipeline failed: {e}")


async def cognitive_run_loop(request: LoopRequest) -> dict:
    """Run the autonomous agent loop (DRY_RUN/SIMULATE/PLAN_ONLY/EXECUTE)."""
    import asyncio

    try:
        from common_lib.modules.cognitive_runtime.services.agent_loop import AgentLoop

        loop = AgentLoop(_get_runtime())
        return asyncio.run(
            loop.run(
                request.task, mode=request.mode, max_iterations=request.max_iterations
            )
        )
    except Exception as e:
        raise Exception(f"Cognitive loop failed: {e}")


def register_cognitive_runtime_tools(mcp) -> int:
    """Register all cognitive runtime tools with the MCP server."""
    tools = [
        (
            "cognitive_infer",
            cognitive_infer,
            "Run a capability inference with budgeted context",
        ),
        (
            "cognitive_decide",
            cognitive_decide,
            "Routed decision via NEXUS with safe fallback",
        ),
        ("cognitive_plan", cognitive_plan, "Build an ExecutionPlan DAG for a task"),
        (
            "cognitive_execute",
            cognitive_execute,
            "Execute an ExecutionPlan DAG with budgets",
        ),
        ("cognitive_run_pipeline", cognitive_run_pipeline, "Run a pipeline DSL spec"),
        ("cognitive_run_loop", cognitive_run_loop, "Run the autonomous agent loop"),
    ]
    count = 0
    for name, func, description in tools:
        try:
            mcp.tool(name=name, description=description)(func)
            count += 1
        except Exception as e:
            print(f"Failed to register {name}: {e}")
    return count
