"""Optimization Runs Routes.

Thin transport layer for run lifecycle management.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common_lib.modules.harness_optimization.service import (
    get_harness_optimization_service,
)
from common_lib.modules.harness_optimization.flags import is_hos_enabled
from common_lib.modules.harness_optimization.exceptions import FeatureDisabledError

from app.modules.harness_optimization.routes.schemas import (
    RunCreate,
    RunRead,
    RunTransition,
    CandidateRead,
    ExecutionRead,
    EvidenceRead,
)

router = APIRouter(prefix="/runs", tags=["Optimization Runs"])


def _get_service():
    """Get HOS service instance."""
    if not is_hos_enabled():
        raise FeatureDisabledError(
            "Harness Optimization Service is disabled",
            flag_name="HARNESS_OPTIMIZATION_ENABLED",
        )
    return get_harness_optimization_service()


# ════════════════════════════════════════════════════════════════════
# Run Lifecycle
# ═══════════════════════════════════════════════════════════════════


@router.post(
    "/",
    response_model=RunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new optimization run",
)
def create_run(payload: RunCreate, service=Depends(_get_service)):
    """Create a new optimization run with eligibility checks and budget validation."""
    run = service.create_optimization_run(
        tenant_id=payload.tenant_id,
        requested_by=payload.requested_by,
        task_id=payload.task_id,
        base_harness_version_id=payload.base_harness_version_id,
        mode=payload.mode,
        recursion_budget_k=payload.recursion_budget_k,
        seed=payload.seed,
        executor_substrate=payload.executor_substrate,
        model_profile_id=payload.model_profile_id,
        evaluation_suite_id=payload.evaluation_suite_id,
        budget=payload.budget.model_dump(),
        promotion_policy=payload.promotion_policy,
        dry_run=payload.dry_run,
    )
    return RunRead.model_validate(run)


@router.get(
    "/",
    response_model=List[RunRead],
    summary="List optimization runs",
)
def list_runs(
    tenant_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    service=Depends(_get_service),
):
    """List optimization runs with optional filters."""
    # Note: service doesn't have list_runs yet
    return []


@router.get(
    "/{run_id}",
    response_model=RunRead,
    summary="Get optimization run by ID",
)
def get_run(run_id: UUID, service=Depends(_get_service)):
    """Get optimization run details."""
    run = service.get_run(run_id)
    return RunRead.model_validate(run)


@router.post(
    "/{run_id}/cancel",
    response_model=RunRead,
    summary="Cancel a running optimization run",
)
def cancel_run(run_id: UUID, service=Depends(_get_service)):
    """Cancel a running optimization run."""
    # Note: service doesn't have cancel_run yet
    from common_lib.modules.harness_optimization.exceptions import HOSError

    raise HOSError("Not implemented yet")


@router.post(
    "/{run_id}/resume",
    response_model=RunRead,
    summary="Resume a run from a checkpoint",
)
def resume_run(run_id: UUID, service=Depends(_get_service)):
    """Resume an optimization run from a checkpoint if fingerprint-compatible."""
    # Note: service doesn't have resume_run yet
    from common_lib.modules.harness_optimization.exceptions import HOSError

    raise HOSError("Not implemented yet")


@router.post(
    "/{run_id}/transition",
    response_model=RunRead,
    summary="Transition run state",
)
def transition_run_state(
    run_id: UUID, payload: RunTransition, service=Depends(_get_service)
):
    """Transition run state with validation."""
    run = service.transition_run_state(run_id, payload.new_status, payload.reason)
    return RunRead.model_validate(run)


# ════════════════════════════════════════════════════════════════════
# Run Execution
# ═══════════════════════════════════════════════════════════════════


@router.post(
    "/{run_id}/execute",
    response_model=dict,
    summary="Execute a full optimization run",
)
async def execute_run(run_id: UUID, service=Depends(_get_service)):
    """Execute a full optimization run with mode-aware behavior."""
    result = await service.execute_run(run_id)
    return result


# ════════════════════════════════════════════════════════════════════
# Candidates & Executions
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/{run_id}/candidates",
    response_model=List[CandidateRead],
    summary="List candidates for a run",
)
def list_candidates(run_id: UUID, service=Depends(_get_service)):
    """List candidate harnesses for a run with their statuses."""
    # Note: service doesn't have list_candidates yet
    return []


@router.get(
    "/{run_id}/executions",
    response_model=List[ExecutionRead],
    summary="List executions for a run",
)
def list_executions(run_id: UUID, service=Depends(_get_service)):
    """List all executions (baseline + probes) for a run."""
    # Note: service doesn't have list_executions yet
    return []


@router.get(
    "/{run_id}/executions/{execution_id}",
    response_model=ExecutionRead,
    summary="Get execution details",
)
def get_execution(run_id: UUID, execution_id: UUID, service=Depends(_get_service)):
    """Get execution details by ID."""
    # Note: service doesn't have get_execution yet
    from common_lib.modules.harness_optimization.exceptions import HOSError

    raise HOSError("Not implemented yet")


# ════════════════════════════════════════════════════════════════════
# Evidence & Contrasts
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/{run_id}/evidence",
    response_model=List[EvidenceRead],
    summary="Get evidence/contrasts for a run",
)
def get_evidence(run_id: UUID, service=Depends(_get_service)):
    """Get evidence items and behavioral contrasts for a run."""
    # Note: service doesn't have get_evidence yet
    return []


@router.get(
    "/{run_id}/report",
    response_model=dict,
    summary="Get run metrics and findings report",
)
def get_run_report(run_id: UUID, service=Depends(_get_service)):
    """Get comprehensive run report with metrics and findings."""
    # Note: service doesn't have get_report yet
    return {}


# ════════════════════════════════════════════════════════════════════
# SSE Event Stream
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/{run_id}/stream",
    summary="SSE event stream for a run",
)
async def stream_run_events(run_id: UUID):
    """Server-Sent Events stream for real-time run updates."""
    from fastapi.responses import StreamingResponse
    from sse_starlette.sse import EventSourceResponse
    import asyncio
    import json

    async def event_generator():
        # This would connect to the real event stream
        # For now, yield a placeholder
        yield {
            "event": "run.status",
            "data": json.dumps(
                {"run_id": str(run_id), "status": "streaming not implemented"}
            ),
        }
        await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


__all__ = ["router"]
