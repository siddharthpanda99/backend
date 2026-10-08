"""Runtime Execution Router — POST /runtime/execute

Thin FastAPI router that delegates to common_lib.modules.runtime for
model execution logic.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/execute", tags=["Runtime — Execution"])


# ──────────────────────────────────────────────────────────────────
# Request / Response Schemas (API-specific)
# ──────────────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    """Request to execute a model inference."""

    model_id: str = Field(..., description="Model identifier")
    plan_id: Optional[str] = Field(default=None, description="Pre-generated execution plan ID")
    inputs: dict[str, Any] = Field(..., description="Model inputs (format depends on model)")
    parameters: Optional[dict[str, Any]] = Field(default=None, description="Generation parameters")
    stream: bool = Field(default=False, description="Stream response")
    request_id: Optional[str] = Field(default=None, description="Request ID for tracing")
    config: Optional[dict[str, Any]] = Field(default=None, description="Execution config overrides")
    use_existing_plan: bool = Field(default=True, description="Use existing plan if available")


class InferenceMetrics(BaseModel):
    """Execution metrics."""

    latency_ms: float = Field(..., description="Total latency in milliseconds")
    tokens_generated: int = Field(default=0, description="Number of tokens generated")
    tokens_per_second: float = Field(default=0.0, description="Throughput")
    time_to_first_token_ms: Optional[float] = Field(default=None, description="TTFT in ms")
    peak_vram_gb: float = Field(default=0.0, description="Peak VRAM usage")
    peak_ram_gb: float = Field(default=0.0, description="Peak RAM usage")


class ExecuteResponse(BaseModel):
    """Response containing inference result and metrics."""

    execution_id: str = Field(..., description="Unique execution identifier")
    plan_id: Optional[str] = Field(default=None, description="Execution plan ID used")
    model_id: str = Field(..., description="Model identifier")
    status: str = Field(..., description="Execution status: success, failed, cancelled")
    output: Any = Field(default=None, description="Model output")
    metrics: InferenceMetrics = Field(..., description="Execution metrics")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    request_id: Optional[str] = Field(default=None, description="Request ID")


# ──────────────────────────────────────────────────────────────────
# Service Accessor
# ──────────────────────────────────────────────────────────────────

def _get_runtime_service():
    """Lazy import of RuntimeService."""
    from common_lib.modules.runtime.service import get_runtime_service
    return get_runtime_service()


def _get_lifecycle_manager():
    """Get the lifecycle manager for model loading/execution."""
    from common_lib.modules.runtime.lifecycle.manager import LifecycleManager, LifecycleManagerConfig
    return LifecycleManager(LifecycleManagerConfig())


# ──────────────────────────────────────────────────────────────────
# Route Handlers
# ──────────────────────────────────────────────────────────────────

@router.post("", response_model=ExecuteResponse, summary="Execute Model Inference")
async def execute_model(request: ExecuteRequest) -> ExecuteResponse:
    """Execute a model inference with the given inputs.

    Flow:
    1. If plan_id provided, validate and use existing plan
    2. Otherwise, generate a plan for the model
    3. Ensure model is loaded (through lifecycle manager)
    4. Execute inference
    5. Return result with metrics
    """
    import time

    execution_id = str(uuid.uuid4())
    request_id = request.request_id or str(uuid.uuid4())

    try:
        service = _get_runtime_service()
        lifecycle = _get_lifecycle_manager()

        # Get or create model
        try:
            model = service.get_model(request.model_id)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Model not found: {request.model_id}") from e

        # Ensure model is in WARM state (loaded and ready)
        model_state = lifecycle.get_model_state(request.model_id)
        if model_state != "warm":
            # Try to load the model
            from common_lib.modules.runtime.lifecycle.manager import ModelLoadRequest
            load_request = ModelLoadRequest(
                model_id=request.model_id,
                model=model,
                warmup=True,
            )
            load_result = lifecycle.load_model(load_request)
            if load_result.status != "loaded":
                raise HTTPException(
                    status_code=503,
                    detail=f"Model load failed: {load_result.error}"
                )

        # Execute inference
        start_time = time.perf_counter()

        result = lifecycle.execute_model(request.model_id, request.inputs)

        execution_time = time.perf_counter() - start_time

        if result is None:
            raise HTTPException(status_code=500, detail="Execution returned no result")

        if "error" in result:
            return ExecuteResponse(
                execution_id=execution_id,
                model_id=request.model_id,
                request_id=request_id,
                status="failed",
                output=None,
                metrics=InferenceMetrics(
                    latency_ms=execution_time * 1000,
                    tokens_generated=0,
                    tokens_per_second=0.0,
                ),
                error=result["error"],
            )

        # Build metrics
        output = result.get("output", result) if isinstance(result, dict) else result
        tokens = 0
        if isinstance(output, str):
            tokens = len(output.split())
        elif isinstance(output, list):
            tokens = len(output)

        metrics = InferenceMetrics(
            latency_ms=execution_time * 1000,
            tokens_generated=tokens,
            tokens_per_second=tokens / execution_time if execution_time > 0 else 0.0,
            peak_vram_gb=0.0,  # Would need device monitoring
            peak_ram_gb=0.0,
        )

        return ExecuteResponse(
            execution_id=execution_id,
            model_id=request.model_id,
            request_id=request_id,
            status="success",
            output=output,
            metrics=metrics,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("execute_model failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/plan", response_model=ExecuteResponse, summary="Execute with Pre-generated Plan")
async def execute_with_plan(
    plan_id: str = Body(..., embed=True),
    inputs: dict[str, Any] = Body(..., embed=True),
    parameters: Optional[dict[str, Any]] = Body(default=None, embed=True),
    request_id: Optional[str] = Body(default=None, embed=True),
) -> ExecuteResponse:
    """Execute inference using a pre-generated execution plan.

    The plan must have been created via POST /runtime/plan and must be in VALID state.
    """
    import time

    execution_id = str(uuid.uuid4())
    req_id = request_id or str(uuid.uuid4())

    try:
        service = _get_runtime_service()
        lifecycle = _get_lifecycle_manager()

        # TODO: In a full implementation, we would retrieve the plan by plan_id
        # from a plan store. For now, we validate the model and execute.

        # For now, extract model_id from the request (would come from plan in full impl)
        # This is a placeholder - real impl would fetch plan from storage
        raise HTTPException(
            status_code=501,
            detail="Plan-based execution not yet implemented — use POST /runtime/execute directly"
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("execute_with_plan failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))