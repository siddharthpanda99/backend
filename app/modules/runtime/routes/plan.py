"""Runtime Planning Router — POST /runtime/plan

Thin FastAPI router that delegates to common_lib.modules.runtime for
execution planning logic.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plan", tags=["Runtime — Planning"])


# ──────────────────────────────────────────────────────────────────
# Request / Response Schemas (API-specific)
# ──────────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    """Request to generate an execution plan."""

    model_id: str = Field(..., description="Model identifier")
    request_id: Optional[str] = Field(default=None, description="Optional request ID for tracing")
    inputs: Optional[dict[str, Any]] = Field(default=None, description="Sample inputs for shape inference")
    config: Optional[dict[str, Any]] = Field(default=None, description="Execution configuration overrides")
    policy: Optional[dict[str, Any]] = Field(default=None, description="Execution policy constraints")
    priority: str = Field(default="normal", description="Execution priority: low, normal, high, critical, realtime")
    strategy_hint: Optional[str] = Field(default=None, description="Optional strategy hint: single_device, data_parallel, tensor_parallel, pipeline_parallel, expert_parallel, hybrid_parallel, speculative_decoding, continuous_batching, prefix_caching")
    enable_fallbacks: bool = Field(default=True, description="Generate fallback plans")


class PlanResponse(BaseModel):
    """Response containing the generated execution plan."""

    plan_id: str = Field(..., description="Unique plan identifier")
    model_id: str = Field(..., description="Model identifier")
    request_id: Optional[str] = Field(default=None, description="Request identifier")
    status: str = Field(..., description="Plan status: pending, validating, valid, invalid, executing, completed, failed, cancelled")
    config: dict[str, Any] = Field(..., description="Execution configuration")
    policy: dict[str, Any] = Field(..., description="Execution policy")
    assigned_devices: list[int] = Field(default_factory=list, description="Assigned device IDs")
    device_pool: Optional[str] = Field(default=None, description="Device pool name")
    memory_estimate: dict[str, Any] = Field(..., description="Memory estimation breakdown")
    confidence: Optional[dict[str, Any]] = Field(default=None, description="Confidence scoring")
    fallback_plans: list[dict[str, Any]] = Field(default_factory=list, description="Fallback plans")
    created_at: str = Field(..., description="Creation timestamp")
    created_by: str = Field(default="planner", description="Plan creator: planner, user, scheduler")


# ──────────────────────────────────────────────────────────────────
# Service Accessor
# ──────────────────────────────────────────────────────────────────

def _get_runtime_service():
    """Lazy import of RuntimeService to avoid circular imports at module load."""
    from common_lib.modules.runtime.service import get_runtime_service
    return get_runtime_service()


def _get_planner():
    """Get or create the execution planner."""
    # The planner is currently part of the service or will be implemented
    # For now we use the service's list_models and hardware discovery
    return _get_runtime_service()


# ──────────────────────────────────────────────────────────────────
# Route Handlers
# ──────────────────────────────────────────────────────────────────

@router.post("", response_model=PlanResponse, summary="Generate Execution Plan")
async def create_execution_plan(request: PlanRequest) -> PlanResponse:
    """Generate an execution plan for a model inference request.

    Returns an ExecutionPlan with:
    - Resource allocation (devices, memory estimates)
    - Execution configuration and policy
    - Confidence scoring with warnings and recommendations
    - Fallback plans for resilience
    """
    try:
        service = _get_runtime_service()

        # Verify model exists
        try:
            model = service.get_model(request.model_id)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Model not found: {request.model_id}") from e

        # Discover hardware if not already done
        hardware = service.discover_hardware()

        # Build execution config from request
        from common_lib.modules.runtime.core.plan import (
            ExecutionConfig,
            ExecutionStrategy,
            ExecutionPriority,
            ExecutionPolicy,
            MemoryEstimate,
            ConfidenceScore,
            ExecutionPlan,
        )

        # Parse strategy hint
        strategy = ExecutionStrategy.SINGLE_DEVICE
        if request.strategy_hint:
            try:
                strategy = ExecutionStrategy(request.strategy_hint)
            except ValueError:
                logger.warning(f"Unknown strategy hint: {request.strategy_hint}")

        # Parse priority
        priority = ExecutionPriority.NORMAL
        try:
            priority = ExecutionPriority(request.priority)
        except ValueError:
            logger.warning(f"Unknown priority: {request.priority}")

        # Build config
        config = ExecutionConfig(
            strategy=strategy,
            priority=priority,
            **(request.config or {}),
        )

        # Build policy
        policy = ExecutionPolicy(**(request.policy or {}))
        policy.allowed_strategies = [strategy] if strategy != ExecutionStrategy.SINGLE_DEVICE else None

        # Estimate memory using the default runtime
        runtime_name = "vllm"  # default
        runtime = service.get_runtime(runtime_name)
        if not runtime:
            # Try to get first available runtime
            runtimes = service.list_runtimes()
            if runtimes:
                runtime = runtimes[0]

        if runtime:
            memory_estimate = runtime.estimate_memory(model, config)
        else:
            # Fallback to base estimation
            from common_lib.modules.runtime.core.runtime import BaseRuntimeAdapter
            memory_estimate = BaseRuntimeAdapter("default", "1.0").estimate_memory(model, config)

        # Calculate confidence
        available_vram = service.get_free_vram_gb()
        total_vram = service.get_total_vram_gb()

        resource_fit = 1.0
        if memory_estimate.total_vram_gb > 0 and available_vram > 0:
            resource_fit = min(1.0, available_vram / memory_estimate.total_vram_gb)

        confidence = ConfidenceScore(
            overall=resource_fit * 0.9,  # Simplified confidence
            resource_fit=resource_fit,
            performance_prediction=0.8,
            reliability=0.9,
            cost_efficiency=0.85,
            factors={
                "vram_available_gb": available_vram,
                "vram_required_gb": memory_estimate.total_vram_gb,
                "model_local": model.is_local,
            },
            warnings=[],
            recommendations=[],
        )

        if not model.is_local:
            confidence.warnings.append("Model is not downloaded locally — download will be required before execution")
            confidence.recommendations.append("Run model download first")

        if memory_estimate.total_vram_gb > available_vram:
            confidence.warnings.append(f"Required VRAM ({memory_estimate.total_vram_gb:.1f}GB) exceeds available ({available_vram:.1f}GB)")
            confidence.recommendations.append("Consider quantization or CPU offload")

        # Generate fallback plans if enabled
        fallback_plans = []
        if request.enable_fallbacks and strategy != ExecutionStrategy.SINGLE_DEVICE:
            # Create CPU fallback
            cpu_config = ExecutionConfig(
                strategy=ExecutionStrategy.SINGLE_DEVICE,
                device_ids=[],
                dtype="auto",
                cpu_offload_gb=memory_estimate.total_vram_gb,
            )
            cpu_memory = runtime.estimate_memory(model, cpu_config) if runtime else memory_estimate
            cpu_confidence = ConfidenceScore(
                overall=0.5,
                resource_fit=1.0,
                performance_prediction=0.3,
                reliability=0.95,
                cost_efficiency=0.9,
            )
            fallback_plan = ExecutionPlan(
                id=str(uuid.uuid4()),
                model_id=request.model_id,
                request_id=request.request_id,
                config=cpu_config,
                policy=policy,
                memory_estimate=cpu_memory,
                confidence=cpu_confidence,
                created_by="planner",
                metadata={"fallback_type": "cpu_offload"},
            )
            fallback_plans.append(fallback_plan.to_dict())

        # Create the main plan
        plan = ExecutionPlan(
            id=str(uuid.uuid4()),
            model_id=request.model_id,
            request_id=request.request_id,
            config=config,
            policy=policy,
            memory_estimate=memory_estimate,
            confidence=confidence,
            fallback_plans=[ExecutionPlan.from_dict(p) for p in fallback_plans],
            created_by="planner",
        )

        return PlanResponse(**plan.to_dict())

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("create_execution_plan failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/validate", response_model=dict, summary="Validate Execution Plan")
async def validate_execution_plan(plan: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Validate an execution plan without creating it.

    Checks:
    - Model exists and is available
    - Required devices are available
    - Memory fits in available VRAM
    - Strategy is supported by runtime
    - Policy constraints are satisfied
    """
    try:
        service = _get_runtime_service()

        model_id = plan.get("model_id")
        if not model_id:
            raise HTTPException(status_code=400, detail="model_id is required")

        try:
            model = service.get_model(model_id)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Model not found: {model_id}") from e

        config = ExecutionConfig.from_dict(plan.get("config", {}))
        policy = ExecutionPolicy.from_dict(plan.get("policy", {}))

        # Check runtime support
        runtime = service.get_runtime("vllm")
        if not runtime:
            runtimes = service.list_runtimes()
            if runtimes:
                runtime = runtimes[0]

        if runtime:
            is_valid, errors = runtime.validate_plan(
                ExecutionPlan.from_dict(plan)
            )
        else:
            is_valid = True
            errors = []

        # Additional validation
        hardware = service.discover_hardware()
        available_vram = service.get_free_vram_gb()

        memory_estimate = MemoryEstimate.from_dict(plan.get("memory_estimate", {}))
        if memory_estimate.total_vram_gb > available_vram:
            is_valid = False
            errors.append(f"Insufficient VRAM: need {memory_estimate.total_vram_gb:.1f}GB, have {available_vram:.1f}GB")

        return {
            "valid": is_valid,
            "errors": errors,
            "model_id": model_id,
            "available_vram_gb": available_vram,
            "required_vram_gb": memory_estimate.total_vram_gb,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("validate_execution_plan failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))