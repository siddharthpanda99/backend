"""Assignments API Router — Thin Transport Layer"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.orchestration.assignments.schemas import (
    AssignmentCreate,
    AssignmentRead,
    WorkerSlotStatus,
    BackgroundJobRead,
    LaunchRequest,
    DeliverRequest,
    ReportRequest,
    RetryRequest,
    StopRequest,
    PrepareCommandRequest,
)
from common_lib.modules.orchestration.assignments.service import get_assignments_service
from common_lib.modules.orchestration.assignments.exceptions import (
    AssignmentsError,
    AssignmentError,
    AssignmentNotFoundError,
    AssignmentAlreadyRunningError,
    AssignmentEndedError,
    NoWorkerSlotAvailableError,
    PrepareError,
    BackgroundJobError,
    DeliveryError,
)

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.post("", response_model=AssignmentRead, status_code=201)
def create_assignment(payload: AssignmentCreate) -> AssignmentRead:
    """Create a new assignment."""
    try:
        svc = get_assignments_service()
        m_id = UUID(payload.mandate_id) if payload.mandate_id else None
        assignment = svc.create_assignment(payload.ticket_id, m_id, payload.meta)
        return AssignmentRead.model_validate(assignment)
    except AssignmentsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{assignment_id}/launch", response_model=AssignmentRead)
def launch_assignment(assignment_id: UUID, payload: LaunchRequest) -> AssignmentRead:
    """Launch an assignment (prepare + start executor)."""
    try:
        svc = get_assignments_service()
        assignment = svc.launch(assignment_id, payload.prepare_command)
        return AssignmentRead.model_validate(assignment)
    except AssignmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except AssignmentAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except NoWorkerSlotAvailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PrepareError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except AssignmentsError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{assignment_id}/deliver")
def deliver_inputs(assignment_id: UUID, payload: DeliverRequest) -> dict[str, Any]:
    """Deliver inputs to a running assignment."""
    try:
        svc = get_assignments_service()
        return svc.deliver_inputs(assignment_id, payload.input_ids)
    except AssignmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except AssignmentEndedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except DeliveryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{assignment_id}/bg-jobs")
def start_bg_job(
    assignment_id: UUID,
    job_type: str = Query(...),
    command: str | None = Query(None),
    is_subagent: bool = Query(False),
    subagent_session_id: str | None = Query(None),
) -> BackgroundJobRead:
    """Start a background job (shell or subagent)."""
    try:
        svc = get_assignments_service()
        job = svc.start_background_job(
            assignment_id, job_type, command, is_subagent, subagent_session_id
        )
        return BackgroundJobRead.model_validate(job)
    except AssignmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except BackgroundJobError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/bg-jobs/{job_id}/complete", response_model=BackgroundJobRead)
def complete_bg_job(
    job_id: UUID, result: dict[str, Any] | None = None, error: str | None = None
) -> BackgroundJobRead:
    """Complete a background job."""
    try:
        svc = get_assignments_service()
        job = svc.complete_background_job(job_id, result, error)
        return BackgroundJobRead.model_validate(job)
    except BackgroundJobError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{assignment_id}/report", response_model=AssignmentRead)
def report(assignment_id: UUID, payload: ReportRequest) -> AssignmentRead:
    """Record a report from executor."""
    try:
        svc = get_assignments_service()
        assignment = svc.report(
            assignment_id,
            payload.state,
            payload.question,
            payload.pr_number,
            payload.output,
            payload.error,
        )
        return AssignmentRead.model_validate(assignment)
    except AssignmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{assignment_id}/retry", response_model=AssignmentRead)
def retry_assignment(assignment_id: UUID, _: RetryRequest) -> AssignmentRead:
    """Retry a failed/blocked/stopped assignment."""
    try:
        svc = get_assignments_service()
        assignment = svc.retry(assignment_id)
        return AssignmentRead.model_validate(assignment)
    except AssignmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except AssignmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{assignment_id}/stop", response_model=AssignmentRead)
def stop_assignment(assignment_id: UUID, payload: StopRequest) -> AssignmentRead:
    """Stop a running assignment."""
    try:
        svc = get_assignments_service()
        assignment = svc.stop(assignment_id, payload.reason)
        return AssignmentRead.model_validate(assignment)
    except AssignmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except AssignmentEndedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/{assignment_id}", response_model=AssignmentRead)
def get_assignment(assignment_id: UUID) -> AssignmentRead:
    """Get an assignment by ID."""
    svc = get_assignments_service()
    assignment = svc.get_assignment(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return AssignmentRead.model_validate(assignment)


@router.get("", response_model=list[AssignmentRead])
def list_assignments(
    ticket_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[AssignmentRead]:
    """List assignments with optional filters."""
    svc = get_assignments_service()
    rows = svc.list_assignments(
        ticket_id=ticket_id, status=status, limit=limit, offset=offset
    )
    return [AssignmentRead.model_validate(r) for r in rows]


@router.get("/worker-status", response_model=WorkerSlotStatus)
def worker_status() -> WorkerSlotStatus:
    """Get worker slot pool status."""
    svc = get_assignments_service()
    return WorkerSlotStatus(**svc.get_worker_status())


@router.get("/health")
def health() -> dict[str, Any]:
    """Get health for all assignments."""
    svc = get_assignments_service()
    health = svc.health()
    return {k: v.model_dump() for k, v in health.items()}
