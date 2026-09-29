"""Cognitive models + evaluation routes — thin router layer.

Missing-surface additions (COGR CHUNK 3.2; infer/decide/plan/execute/runs
already covered by sibling route files):

* ``GET /cognitive/models/capabilities`` — capability inventory + datasets
* ``POST /cognitive/models/register`` — register + mark REGISTERED
* ``POST /cognitive/models/certify`` — run the certification pipeline
* ``POST /cognitive/evaluate`` — benchmark one capability
* ``GET /cognitive/telemetry/aggregates`` — quality priors for the dashboard
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["Cognitive Models & Eval"])


class ModelRegisterRequest(BaseModel):
    model_id: str = Field(min_length=1)
    name: str = ""
    provider: str = "local"
    version: str = "1.0"
    capabilities: list[str] = Field(default_factory=list)


class ModelCertifyRequest(BaseModel):
    model_id: str = Field(min_length=1)
    benchmark: dict[str, Any] | None = None
    approve: bool = False
    min_accuracy: float = 0.7


class EvaluateRequest(BaseModel):
    model_id: str = ""
    capability: str = "general"
    cases: dict[str, Any] = Field(default_factory=dict)
    min_accuracy: float = 0.7


@router.get("/models/capabilities")
async def list_capabilities():
    """Capability inventory with eval-dataset sizes."""
    try:
        from common_lib.modules.integration.ports.evaluation.evaluation_port import (
            get_cognitive_datasets,
        )

        return {"capabilities": get_cognitive_datasets()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Capabilities failed: {e}")


@router.post("/models/register")
async def register_model(request: ModelRegisterRequest):
    """Register a model and mark it REGISTERED (never auto-production)."""
    try:
        from common_lib.modules.ai_models.registry.certification import (
            ModelLifecycleState,
            certify,
            lifecycle_state_of,
        )

        container_model: dict[str, Any] | None = None
        try:
            from common_lib.modules.ai_models.container import (
                AIModelsContainer,
            )
            from common_lib.modules.ai_models.domain.entities import ModelEntity

            entity = ModelEntity(
                id=request.model_id,
                name=request.name or request.model_id,
                provider=request.provider,
                version=request.version,
                modality="text",
                tasks=[],
                capabilities=list(request.capabilities or []),
            )
            AIModelsContainer().registry_service.register_model(entity)
            container_model = entity.model_dump()
        except Exception as reg_exc:  # noqa: BLE001 — registry best-effort
            container_model = {"warning": f"catalog register skipped: {reg_exc}"}
        certify(request.model_id, ModelLifecycleState.REGISTERED)
        return {
            "model_id": request.model_id,
            "lifecycle_state": lifecycle_state_of(request.model_id).value,
            "catalog": container_model,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Register failed: {e}")


@router.post("/models/certify")
async def certify_model(request: ModelCertifyRequest):
    """Run the certification pipeline (fail-closed on missing gates)."""
    try:
        from common_lib.modules.ai_models.registry.certify_pipeline import (
            run_certification,
        )

        report = run_certification(
            request.model_id,
            benchmark_cases=request.benchmark,
            security_scanner=None,
            governance_approver=(lambda mid: True) if request.approve else None,
            min_accuracy=request.min_accuracy,
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Certify failed: {e}")


@router.post("/evaluate")
async def evaluate_capability(request: EvaluateRequest):
    """Benchmark one capability via the evaluation harness."""
    try:
        from common_lib.modules.integration.ports.evaluation.evaluation_port import (
            run_capability_benchmark,
        )

        cases = dict(request.cases or {})
        cases.setdefault("capability", request.capability)
        result = run_capability_benchmark(
            model_id=request.model_id or None,
            cases=cases,
            min_accuracy=request.min_accuracy,
        )
        if not result:
            raise HTTPException(
                status_code=503, detail="Evaluation harness unavailable"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluate failed: {e}")


@router.get("/telemetry/aggregates")
async def telemetry_aggregates(capability: str | None = None):
    """Quality priors per (model, capability) for routing + dashboard."""
    try:
        from common_lib.modules.integration.ports.cognitive_runtime.cognitive_runtime_port import (
            get_telemetry_aggregates,
        )

        return {
            "priors": get_telemetry_aggregates(capability=capability),
            "capability": capability,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregates failed: {e}")
