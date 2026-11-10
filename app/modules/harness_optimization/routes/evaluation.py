"""Evaluation Routes.

Thin transport layer for execution evaluation.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status

from common_lib.modules.harness_optimization.service import (
    get_harness_optimization_service,
)
from common_lib.modules.harness_optimization.flags import (
    is_hos_enabled,
    is_evaluation_enabled,
)
from common_lib.modules.harness_optimization.exceptions import FeatureDisabledError

from app.modules.harness_optimization.routes.schemas import (
    EvaluationRequest,
    EvaluationRead,
)

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


def _get_service():
    """Get HOS service instance."""
    if not is_hos_enabled() or not is_evaluation_enabled():
        raise FeatureDisabledError(
            "Evaluation feature is disabled",
            flag_name="HARNESS_OPT_EVALUATION_ENABLED",
        )
    return get_harness_optimization_service()


# ════════════════════════════════════════════════════════════════════
# Evaluation
# ═══════════════════════════════════════════════════════════════════


@router.post(
    "/",
    response_model=EvaluationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Run evaluation of an execution through all gates",
)
async def evaluate_execution(payload: EvaluationRequest, service=Depends(_get_service)):
    """Run evaluation of an execution through all gates."""
    result = await service.evaluate_execution(
        run_id=payload.run_id,
        harness_version_id=payload.harness_version_id,
        execution_id=payload.execution_id,
        baseline_execution_id=payload.baseline_execution_id,
        candidate_execution_id=payload.candidate_execution_id,
        evaluator_suite_id=payload.evaluator_suite_id,
    )
    return EvaluationRead(**result)


@router.post(
    "/metrics/register",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Register a custom HOS metric calculator",
)
async def register_metric_calculator(
    name: str,
    service=Depends(_get_service),
):
    """Register a custom HOS metric calculator for evaluation."""
    # Note: the actual calculator function would need to be passed
    # This is a simplified endpoint
    await service.register_metric_calculator(name, None)
    return {"registered": True}


__all__ = ["router"]
