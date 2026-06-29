"""Kimchi API router — Scoping / Execution / Grading / HITL endpoints.

Pattern follows ``workflows/routes/index.py`` (thin router delegating to
common_lib services). All endpoints live under ``/api/v1/kimchi/``.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Body, Query
from pydantic import BaseModel

from common_lib.modules.ferment.state import (
    FermentProject,
    Phase,
    Step,
    StepStatus,
    ContinuationPolicy,
)
from common_lib.modules.ferment.executor import FermentExecutor
from common_lib.modules.ferment.scoping import ScopingLoop
from common_lib.modules.ferment.grading import GradingJudge, GradingResult, Grade
from common_lib.modules.ferment.persistence import save_project, load_project, update_project, delete_project

# ── Integration module wiring ──────────────────────────────────────
from common_lib.modules.integration import (
    get_event_router,
    get_context_propagation,
    create_trace_context,
    get_error_handler,
    ErrorSeverity,
)
from common_lib.modules.integration.adapters.kimchi_bridge import (
    ensure_kimchi_bridge_registered,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Auto-register Kimchi event handlers upon module import
ensure_kimchi_bridge_registered()


# =========================================================================
# Request / Response schemas
# =========================================================================


class ScopeRequest(BaseModel):
    """Request to kick off a scoping loop."""
    goal: str
    auto_approve: bool = True
    continuation: str = "automated"  # "automated" | "manual"


class ExecuteRequest(BaseModel):
    """Request to run a previously scoped project."""
    project_name: str
    base_dir: str = ""
    auto_run: bool = True  # True = run_until_blocked, False = run_one_step
    hitl_action: Optional[str] = None  # "retry" | "skip" | "abort" — for HITL stuck steps


class GradeRequest(BaseModel):
    """Request to grade completed steps."""
    project_name: str
    base_dir: str = ""
    step_ids: Optional[List[str]] = None  # None = all steps


class GradeResponse(BaseModel):
    """Per-step grade result."""
    step_id: str
    step_name: str
    grade: str
    rubric_scores: Dict[str, float]
    rationale: str
    suggestions: List[str]


class PhaseGrade(BaseModel):
    """Aggregated grade for an entire phase."""
    phase_name: str
    grade: str
    rationale: str


class PipelineResponse(BaseModel):
    """Top-level pipeline response."""
    status: str
    project_name: str
    phases: List[Dict[str, Any]]
    progress: str = ""
    error: Optional[str] = None
    awaiting_input: bool = False
    grades: Optional[List[GradeResponse]] = None
    phase_grades: Optional[List[PhaseGrade]] = None
    trace_id: Optional[str] = None


# =========================================================================
# ── Scoping endpoints ────────────────────────────────────────────────
# =========================================================================


@router.post("/scope", response_model=PipelineResponse)
async def create_scope(req: ScopeRequest) -> Dict[str, Any]:
    """Run the scoping loop: orient → interview → plan → approve.

    Returns a fully populated FermentProject with phased steps.
    """
    ctx = create_trace_context(source="api", operation="kimchi.scope")
    trace_id = ctx.trace_id

    try:
        loop = ScopingLoop(
            goal=req.goal,
            auto_approve=req.auto_approve,
            continuation=ContinuationPolicy.AUTOMATED
            if req.continuation == "automated"
            else ContinuationPolicy.MANUAL,
        )
        project = await loop.run()

        # Fire integration event
        try:
            router_ = get_event_router()
            await router_.fire_event(
                event_type="kimchi.scope.completed",
                data={
                    "project_name": project.name,
                    "phase_count": len(project.phases),
                    "step_count": sum(len(p.steps) for p in project.phases),
                },
                channel="workflow",
                trace_id=trace_id,
            )
        except Exception:
            logger.warning("Failed to fire scoping event", exc_info=True)

        save_project(project, base_dir="")

        return _project_to_response(
            project=project,
            status="scoped",
            trace_id=trace_id,
        )

    except Exception as exc:
        logger.error("Scoping failed: %s", exc, exc_info=True)
        get_error_handler().handle_error(
            error=exc,
            module="kimchi",
            operation="scope",
            severity=ErrorSeverity.ERROR,
        )
        raise HTTPException(status_code=500, detail=str(exc))


# =========================================================================
# ── Execution endpoints ──────────────────────────────────────────────
# =========================================================================


@router.post("/execute", response_model=PipelineResponse)
async def execute_project(req: ExecuteRequest) -> Dict[str, Any]:
    """Execute a scoped project step by step.

    Returns intermediate results. If a step blocks and the project has
    HITL enabled, polls for user decision.
    """
    ctx = create_trace_context(source="api", operation="kimchi.execute")
    trace_id = ctx.trace_id

    project = load_project(req.project_name, base_dir=req.base_dir)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{req.project_name}' not found. Run /kimchi/scope first.",
        )

    try:
        executor = FermentExecutor(
            project=project,
            step_runner=_default_step_runner,
            base_dir=req.base_dir,
            hitl_callback=_build_hitl_callback(project),
        )

        if req.auto_run:
            result = executor.run_until_blocked()
        else:
            result = executor.run_one_step()

        save_project(project, base_dir=req.base_dir)

        # Fire integration event
        try:
            router_ = get_event_router()
            await router_.fire_event(
                event_type="kimchi.execute.completed",
                data={
                    "project_name": project.name,
                    "status": result["status"],
                    "progress": result.get("progress", ""),
                },
                channel="workflow",
                trace_id=trace_id,
            )
        except Exception:
            logger.warning("Failed to fire execution event", exc_info=True)

        return {
            **_project_to_response(project, result["status"], trace_id),
            "progress": result.get("progress", ""),
            "error": result.get("error"),
            "awaiting_input": result.get("awaiting_input", False),
            "step_id": result.get("step_id"),
            "step_name": result.get("step_name"),
        }

    except Exception as exc:
        logger.error("Execution failed: %s", exc, exc_info=True)
        get_error_handler().handle_error(
            error=exc, module="kimchi", operation="execute", severity=ErrorSeverity.ERROR
        )
        raise HTTPException(status_code=500, detail=str(exc))


# =========================================================================
# ── Grading endpoints ────────────────────────────────────────────────
# =========================================================================


@router.post("/grade", response_model=PipelineResponse)
async def grade_project(req: GradeRequest) -> Dict[str, Any]:
    """Evaluate completed steps with A–F letter grades.

    Optionally filter specific step_ids. Returns rubric scores,
    suggestions, and phase-level aggregation.
    """
    ctx = create_trace_context(source="api", operation="kimchi.grade")
    trace_id = ctx.trace_id

    project = load_project(req.project_name, base_dir=req.base_dir)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{req.project_name}' not found.",
        )

    try:
        judge = GradingJudge()
        grades: List[GradeResponse] = []
        step_ids = set(req.step_ids) if req.step_ids else None

        for phase in project.phases:
            for step in phase.steps:
                if step_ids and step.id not in step_ids:
                    continue
                if step.status != StepStatus.COMPLETED:
                    continue

                result = judge.evaluate_step(
                    step_name=step.name,
                    step_description=step.description,
                    step_result=step.result,
                )
                grades.append(
                    GradeResponse(
                        step_id=step.id,
                        step_name=step.name,
                        grade=result.grade.value,
                        rubric_scores=result.rubric_scores,
                        rationale=result.rationale,
                        suggestions=result.suggestions,
                    )
                )

        # Also grade each phase
        phase_grades = []
        for phase in project.phases:
            completed_steps = [
                {"name": s.name, "description": s.description, "result": s.result}
                for s in phase.steps
                if s.status == StepStatus.COMPLETED
            ]
            if completed_steps:
                pg = judge.evaluate_phase(
                    phase_name=phase.name,
                    phase_description=phase.description,
                    step_results=completed_steps,
                )
                phase_grades.append({
                    "phase_name": phase.name,
                    "grade": pg.grade.value,
                    "rationale": pg.rationale,
                })

        # Fire integration event
        try:
            router_ = get_event_router()
            await router_.fire_event(
                event_type="kimchi.grade.completed",
                data={
                    "project_name": project.name,
                    "grade_count": len(grades),
                    "phase_grade_count": len(phase_grades),
                },
                channel="workflow",
                trace_id=trace_id,
            )
        except Exception:
            logger.warning("Failed to fire grading event", exc_info=True)

        return {
            **_project_to_response(project, "graded", trace_id),
            "grades": [g.model_dump() for g in grades],
            "phase_grades": phase_grades,
        }

    except Exception as exc:
        logger.error("Grading failed: %s", exc, exc_info=True)
        get_error_handler().handle_error(
            error=exc, module="kimchi", operation="grade", severity=ErrorSeverity.ERROR
        )
        raise HTTPException(status_code=500, detail=str(exc))


# =========================================================================
# ── Project list / status endpoints ──────────────────────────────────
# =========================================================================


@router.get("/projects", response_model=List[Dict[str, Any]])
async def list_projects(base_dir: str = "") -> List[Dict[str, Any]]:
    """List all Ferment projects saved on disk."""
    import json
    from pathlib import Path
    from common_lib.modules.ferment.persistence import _FERMENT_DIR

    scan_dir = Path(base_dir) if base_dir else Path(_FERMENT_DIR)
    projects = []
    if scan_dir.exists() and scan_dir.is_dir():
        for f in sorted(scan_dir.glob("*.ferment.json")):
            try:
                data = json.loads(f.read_text())
                projects.append({
                    "name": data.get("name", f.stem),
                    "goal": data.get("goal", ""),
                    "phase_count": len(data.get("phases", [])),
                    "status": data.get("status", "unknown"),
                    "updated_at": data.get("updated_at", ""),
                })
            except Exception:
                pass
    return projects


@router.get("/projects/{project_name}", response_model=PipelineResponse)
async def get_project_status(
    project_name: str, base_dir: str = ""
) -> Dict[str, Any]:
    """Get the current status of a Ferment project."""
    project = load_project(project_name, base_dir=base_dir)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")
    return _project_to_response(project, project.status.value)


class UpdateProjectRequest(BaseModel):
    """Request to update an existing Ferment project."""
    goal: Optional[str] = None
    scoping: Optional[Dict[str, Any]] = None
    phases: Optional[List[Dict[str, Any]]] = None
    name: Optional[str] = None
    continuation: Optional[str] = None


@router.put("/projects/{project_name}", response_model=PipelineResponse)
async def update_project_endpoint(
    project_name: str,
    req: UpdateProjectRequest,
    base_dir: str = "",
) -> Dict[str, Any]:
    """Update an existing Ferment project's metadata, phases, or goal.

    Accepts partial updates — only fields present in the request body
    will be modified. Returns the updated project state.
    """
    ctx = create_trace_context(source="api", operation="kimchi.update")

    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    project = update_project(project_name, updates, base_dir=base_dir)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")

    logger.info("Project %s updated: %s", project_name, list(updates.keys()))

    # Fire integration event
    try:
        router_ = get_event_router()
        await router_.fire_event(
            event_type="kimchi.update.completed",
            data={
                "project_name": project.name,
                "updated_fields": list(updates.keys()),
            },
            channel="workflow",
            trace_id=ctx.trace_id,
        )
    except Exception:
        logger.warning("Failed to fire update event", exc_info=True)

    return _project_to_response(project, project.status.value, trace_id=ctx.trace_id)


@router.delete("/projects/{project_name}")
async def delete_project_endpoint(
    project_name: str, base_dir: str = ""
) -> Dict[str, Any]:
    """Delete a Ferment project by name."""
    success = delete_project(project_name, base_dir=base_dir)
    if not success:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")
    return {"status": "deleted", "project_name": project_name}


# =========================================================================
# ── HITL callback endpoint (poll-based) ──────────────────────────────
# =========================================================================


# In-memory store for HITL decisions + threading events, keyed by project_name
_hitl_decisions: Dict[str, Dict[str, Any]] = {}
_hitl_events: Dict[str, threading.Event] = {}


@router.post("/hitl/decision")
async def submit_hitl_decision(
    project_name: str = Body(...),
    action: str = Body(...),  # "retry" | "skip" | "abort"
) -> Dict[str, Any]:
    """Submit a user decision for a stuck step.

    Call this from the UI when the user is prompted via
    ``awaiting_input=true`` in the execute response.
    Wakes up the blocking HITL callback via a threading.Event.
    """
    if action not in ("retry", "skip", "abort"):
        raise HTTPException(status_code=400, detail="action must be 'retry', 'skip', or 'abort'")
    _hitl_decisions[project_name] = {"action": action}
    # Wake up the callback if it's waiting
    event = _hitl_events.get(project_name)
    if event:
        event.set()
    return {"status": "acknowledged", "action": action}


# =========================================================================
# ── Helpers ───────────────────────────────────────────────────────────
# =========================================================================


def _project_to_response(
    project: FermentProject,
    status: str,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a standard pipeline response from a FermentProject."""
    return {
        "status": status,
        "project_name": project.name,
        "project_goal": project.goal,
        "phases": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "status": p.status.value if p.status else "pending",
                "steps": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "description": s.description,
                        "status": s.status.value if s.status else "pending",
                        "result": s.result,
                        "error": s.error,
                        "retry_count": s.retry_count,
                        "grade": s.grade.value if s.grade else None,
                    }
                    for s in p.steps
                ],
            }
            for p in project.phases
        ],
        "continuation": project.continuation.value if project.continuation else "automated",
        "progress": project.progress,
        "trace_id": trace_id,
    }


def _default_step_runner(step: Step, project: FermentProject) -> dict:
    """Default step runner — logs and returns a placeholder.

    In production this would invoke the actual tool / agent / model.
    """
    logger.info("[kimchi] Executing step %r ('%s')", step.id, step.name)
    return {"status": "ok", "result": f"Executed: {step.name}"}


def _build_hitl_callback(project: FermentProject):
    """Build a HITL callback that waits for user decisions via threading.Event.

    Uses ``threading.Event.wait()`` (GIL-releasing) so the FastAPI event loop
    can continue processing other requests while the HITL callback blocks.
    When the user submits a decision via ``POST /hitl/decision``, the event
    is signalled and the callback returns immediately.
    """

    def _callback(step, phase, retry_count, limit):
        # First check if a decision was already submitted (e.g. user responded
        # before the executor reached the stuck step)
        decision = _hitl_decisions.pop(project.name, None)
        if decision:
            return decision

        event = threading.Event()
        _hitl_events[project.name] = event

        try:
            # Wait up to 5 minutes for a decision (Event.wait() releases GIL)
            if event.wait(timeout=300):
                decision = _hitl_decisions.pop(project.name, None)
                return decision or {"action": "abort"}
        finally:
            _hitl_events.pop(project.name, None)

        return {"action": "abort"}

    return _callback
