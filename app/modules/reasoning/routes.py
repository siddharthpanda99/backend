"""Reasoning Mode — REST API routes.

Mounted at ``/api/v1/reasoning``. All logic delegates to
``common_lib.modules.reasoning`` (thin-router convention).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.reasoning import ReasoningPlannerService
from common_lib.modules.reasoning.features import get_reasoning_flags

logger = logging.getLogger(__name__)

router = APIRouter()


def _service() -> ReasoningPlannerService:
    return ReasoningPlannerService()


def _builder_service():
    from common_lib.modules.reasoning.builder import ReasoningBuilderService

    return ReasoningBuilderService()


# ── Request/response schemas ───────────────────────────────────────────────


class PlanCreateRequest(BaseModel):
    request_text: str = Field(..., min_length=1, max_length=16384)
    session_id: Optional[str] = Field(default="", max_length=128)
    context: Optional[Dict[str, Any]] = None
    use_llm: Optional[bool] = True
    # Reasoning Builder grounding (optional): the template whose reasoning
    # instructions guided this plan, plus the structured builder output.
    template_id: Optional[str] = Field(default="", max_length=64)
    instructions: Optional[List[str]] = None
    reasoning_output: Optional[Dict[str, Any]] = None


class TemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    instructions: Optional[str] = Field(default="", max_length=16384)
    description: Optional[str] = Field(default="", max_length=2000)
    level: Optional[str] = Field(default="brief", max_length=16)
    output_format: Optional[str] = Field(default="json", max_length=16)
    topics: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    instructions: Optional[str] = None
    description: Optional[str] = None
    level: Optional[str] = None
    output_format: Optional[str] = None
    topics: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class BuilderRunRequest(BaseModel):
    request_text: str = Field(..., min_length=1, max_length=16384)
    topics: Optional[List[str]] = None
    template_id: Optional[str] = Field(default="", max_length=64)
    # None → fall back to the template's defaults (when a template is used).
    level: Optional[str] = Field(default=None, max_length=16)
    output_format: Optional[str] = Field(default=None, max_length=16)
    session_id: Optional[str] = Field(default="", max_length=128)
    use_llm: Optional[bool] = True


class ItemStatusRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=32)


class ExplainRequest(BaseModel):
    step: Dict[str, Any]
    request_text: Optional[str] = ""
    use_llm: Optional[bool] = True


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/flags", tags=["Reasoning"])
async def list_flags() -> Dict[str, Any]:
    """List all Reasoning Mode feature flags and their current state.

    Lets the UI show/hide the builder, templates, resume and deep-trace
    surfaces based on the flag configuration.
    """
    flags = get_reasoning_flags()
    return {
        "flags": flags.list_all(),
        "snapshot": flags.snapshot(),
    }


@router.put("/flags/{flag_id}", tags=["Reasoning"])
async def set_flag(flag_id: str, req: Dict[str, Any]) -> Dict[str, Any]:
    """Toggle a Reasoning Mode feature flag at runtime."""
    enabled = bool((req or {}).get("enabled", True))
    flags = get_reasoning_flags()
    if not flags.set_flag(flag_id, enabled):
        raise HTTPException(status_code=404, detail=f"Unknown flag: {flag_id}")
    return {
        "flag_id": flag_id,
        "enabled": enabled,
        "snapshot": flags.snapshot(),
    }


@router.post("/plan", tags=["Reasoning"])
async def create_plan(req: PlanCreateRequest) -> Dict[str, Any]:
    """Create a Requirements & Plan document for a request (Reasoning Mode)."""
    result = _service().create_plan(
        request_text=req.request_text,
        session_id=req.session_id or "",
        context=req.context or {},
        use_llm=bool(req.use_llm),
        template_id=req.template_id or "",
        instructions=req.instructions or None,
        reasoning_output=req.reasoning_output or None,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/plans", tags=["Reasoning"])
async def list_plans(session_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """List reasoning plans, newest first (optionally filtered by session)."""
    return _service().list_plans(session_id=session_id, limit=limit)


@router.get("/plans/{plan_id}", tags=["Reasoning"])
async def get_plan(plan_id: str) -> Dict[str, Any]:
    """Get a full reasoning plan (requirements checklist + step plan)."""
    plan = _service().get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return plan


@router.post("/plans/{plan_id}/steps/{step_id}/status", tags=["Reasoning"])
async def set_step_status(
    plan_id: str, step_id: str, req: ItemStatusRequest
) -> Dict[str, Any]:
    """Update the status of one plan step."""
    plan = _service().update_step_status(plan_id, step_id, req.status)
    if plan is None:
        raise HTTPException(
            status_code=404, detail="Plan or step not found / invalid status"
        )
    return plan


@router.post("/plans/{plan_id}/requirements/{requirement_id}/status", tags=["Reasoning"])
async def set_requirement_status(
    plan_id: str, requirement_id: str, req: ItemStatusRequest
) -> Dict[str, Any]:
    """Update the status of one checklist requirement."""
    plan = _service().update_requirement_status(plan_id, requirement_id, req.status)
    if plan is None:
        raise HTTPException(
            status_code=404, detail="Plan or requirement not found / invalid status"
        )
    return plan


@router.delete("/plans/{plan_id}", tags=["Reasoning"])
async def delete_plan(plan_id: str) -> Dict[str, Any]:
    """Delete a reasoning plan."""
    deleted = _service().delete_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return {"deleted": True, "id": plan_id}


@router.post("/explain", tags=["Reasoning"])
async def explain_step(req: ExplainRequest) -> Dict[str, str]:
    """Brief one-level explanation of a step the agent is about to take."""
    explanation = _service().explain_step(
        req.step or {}, req.request_text or "", use_llm=bool(req.use_llm)
    )
    return {"explanation": explanation}


# ── Resume / time-travel (partial runs) ────────────────────────────────────


@router.get("/plans/{plan_id}/resume", tags=["Reasoning"])
async def get_resume_state(plan_id: str) -> Dict[str, Any]:
    """Compute where a plan should resume (failed/in_progress/pending step)."""
    state = _service().get_resume_state(plan_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return state


@router.post("/plans/{plan_id}/resume", tags=["Reasoning"])
async def resume_plan(
    plan_id: str, req: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Resume a plan from a step (auto-computed when no step_id is given)."""
    step_id = (req or {}).get("step_id") if isinstance(req, dict) else None
    plan = _service().resume_plan(plan_id, step_id=step_id or None)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return plan


# ── Reasoning Builder: templates ───────────────────────────────────────────


@router.get("/templates", tags=["Reasoning"])
async def list_templates(
    include_inactive: bool = False, limit: int = 100
) -> List[Dict[str, Any]]:
    """List reasoning templates (CRUD)."""
    return _builder_service().list_templates(
        include_inactive=include_inactive, limit=limit
    )


@router.post("/templates", tags=["Reasoning"])
async def create_template(req: TemplateCreateRequest) -> Dict[str, Any]:
    """Create a reasoning template (instructions passed to agents in Reasoning Mode)."""
    result = _builder_service().create_template(
        name=req.name,
        instructions=req.instructions or "",
        description=req.description or "",
        level=req.level or "brief",
        output_format=req.output_format or "json",
        topics=req.topics or None,
        tags=req.tags or None,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/templates/{template_id}", tags=["Reasoning"])
async def get_template(template_id: str) -> Dict[str, Any]:
    """Get one reasoning template."""
    template = _builder_service().get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    return template


@router.put("/templates/{template_id}", tags=["Reasoning"])
async def update_template(
    template_id: str, req: TemplateUpdateRequest
) -> Dict[str, Any]:
    """Update a reasoning template (partial)."""
    updates = req.model_dump(exclude_unset=True, exclude_none=True)
    template = _builder_service().update_template(template_id, updates)
    if template is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    return template


@router.delete("/templates/{template_id}", tags=["Reasoning"])
async def delete_template(template_id: str) -> Dict[str, Any]:
    """Delete a reasoning template."""
    deleted = _builder_service().delete_template(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    return {"deleted": True, "id": template_id}


# ── Reasoning Builder: runs ────────────────────────────────────────────────


@router.post("/builder/run", tags=["Reasoning"])
async def builder_run(req: BuilderRunRequest) -> Dict[str, Any]:
    """Run the Reasoning Builder: topics → structured output in a format."""
    result = _builder_service().run_reasoning(
        request_text=req.request_text,
        topics=req.topics or None,
        template_id=req.template_id or "",
        level=req.level,
        output_format=req.output_format,
        session_id=req.session_id or "",
        use_llm=bool(req.use_llm),
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/builder/runs", tags=["Reasoning"])
async def list_builder_runs(
    session_id: str = "", template_id: str = "", limit: int = 50
) -> List[Dict[str, Any]]:
    """List reasoning-builder runs, newest first."""
    return _builder_service().list_runs(
        session_id=session_id, template_id=template_id, limit=limit
    )


@router.get("/builder/runs/{run_id}", tags=["Reasoning"])
async def get_builder_run(run_id: str) -> Dict[str, Any]:
    """Get one reasoning-builder run (structured output)."""
    run = _builder_service().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


@router.delete("/builder/runs/{run_id}", tags=["Reasoning"])
async def delete_builder_run(run_id: str) -> Dict[str, Any]:
    """Delete a reasoning-builder run."""
    deleted = _builder_service().delete_run(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return {"deleted": True, "id": run_id}


@router.post("/builder/runs/{run_id}/export", tags=["Reasoning"])
async def export_builder_run(
    run_id: str, req: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Export a reasoning-builder run into a document (json/markdown/text)."""
    fmt = (req or {}).get("format") if isinstance(req, dict) else None
    artifact = _builder_service().export_run(run_id, format=fmt or "markdown")
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return artifact
