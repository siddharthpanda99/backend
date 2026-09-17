"""Decision Fabric routes — DF-030 (spec §56) + DF-056 coordination routes.

THIN transport layer only (platform boundary rule): every endpoint delegates
to common_lib decision_engine services. Zero business logic lives here.
All endpoints are guarded by the NEXUS_DECISION_FABRIC_ENABLED flag
(coordination endpoints additionally by NEXUS_FF_DECISION_COORDINATION_ENABLED);
the flag resolves OFF when the registry is unreachable (fail-closed), so the
whole surface stays inert until the fabric is explicitly enabled.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from common_lib.modules.decision_engine.flags import (
    NEXUS_DECISION_FABRIC_ENABLED,
    is_decision_flag_enabled,
)

router = APIRouter()

COORDINATION_FLAG = "NEXUS_FF_DECISION_COORDINATION_ENABLED"


def _require_fabric() -> None:
    """Fail-closed flag guard: 503 until NEXUS_DECISION_FABRIC_ENABLED is on."""
    if not is_decision_flag_enabled(NEXUS_DECISION_FABRIC_ENABLED):
        raise HTTPException(
            status_code=503,
            detail="Decision Fabric is disabled (NEXUS_DECISION_FABRIC_ENABLED=off)",
        )


def _require_coordination() -> None:
    _require_fabric()
    if not is_decision_flag_enabled(COORDINATION_FLAG):
        raise HTTPException(
            status_code=503,
            detail="Decision coordination is disabled (NEXUS_FF_DECISION_COORDINATION_ENABLED=off)",
        )


# ── §56 Plan endpoints (9) ────────────────────────────────────────────────


@router.post("/plans")
async def create_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST /plans — create a plan from a goal (§56 create)."""
    from common_lib.modules.decision_engine.approval import service as approval

    _require_fabric()
    goal = str(payload.get("goal", "")).strip()
    if not goal:
        raise HTTPException(status_code=422, detail="goal is required")
    plan_id = str(payload.get("plan_id") or f"plan_{abs(hash(goal)) % 10**10}")
    status = str(payload.get("status", "REVIEW_REQUIRED"))
    from common_lib.modules.decision_engine.contracts import DecisionPlan

    plan = DecisionPlan(plan_id=plan_id, goal=goal, status=status)
    approval.create_plan_version(plan.to_dict(), author=str(payload.get("requester", "api")))
    return {"plan_id": plan_id, "status": status}


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str, version: Optional[int] = None) -> Dict[str, Any]:
    """GET /plans/{plan_id} — fetch a plan version (§56 get)."""
    from common_lib.modules.decision_engine.approval import service as approval

    _require_fabric()
    plan = approval.GLOBAL_REGISTRY.get(plan_id, version)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"plan {plan_id!r} not found")
    return plan.to_dict()


@router.post("/plans/{plan_id}/validate")
async def validate_plan(plan_id: str) -> Dict[str, Any]:
    """POST /plans/{plan_id}/validate — run the 14 §81 rules."""
    from common_lib.modules.decision_engine.approval import service as approval
    from common_lib.modules.decision_engine.graph.validator import validate_plan_graph

    _require_fabric()
    plan = approval.GLOBAL_REGISTRY.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"plan {plan_id!r} not found")
    return validate_plan_graph(plan.to_dict())


@router.post("/plans/{plan_id}/approve")
async def approve_plan(plan_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """POST /plans/{plan_id}/approve — §18 approval transition."""
    from common_lib.modules.decision_engine.approval.service import review_plan

    _require_fabric()
    body = payload or {}
    result = review_plan(
        plan_id,
        "approve",
        reviewer=str(body.get("reviewer", "user")),
        comments=str(body.get("comments", "")),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("error", "approve failed"))
    return result


@router.post("/plans/{plan_id}/reject")
async def reject_plan(plan_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """POST /plans/{plan_id}/reject — §18 rejection transition."""
    from common_lib.modules.decision_engine.approval.service import review_plan

    _require_fabric()
    body = payload or {}
    result = review_plan(
        plan_id,
        "reject",
        reviewer=str(body.get("reviewer", "user")),
        comments=str(body.get("comments", "")),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("error", "reject failed"))
    return result


@router.patch("/plans/{plan_id}")
async def edit_plan(plan_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """PATCH /plans/{plan_id} — §47 edit action → new version (§19)."""
    from common_lib.modules.decision_engine.approval.service import review_plan

    _require_fabric()
    action = str(payload.get("action", "edit"))
    result = review_plan(
        plan_id,
        action,
        reviewer=str(payload.get("reviewer", "user")),
        comments=str(payload.get("comments", "")),
        changes=list(payload.get("changes") or []),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("error", "edit failed"))
    return result


@router.post("/plans/{plan_id}/compile")
async def compile_plan(plan_id: str) -> Dict[str, Any]:
    """POST /plans/{plan_id}/compile — approved plan → ExecutionGraph (§35)."""
    from common_lib.modules.decision_engine.approval import service as approval
    from common_lib.modules.decision_engine.execution.compiler import compile_plan as _compile

    _require_fabric()
    plan = approval.GLOBAL_REGISTRY.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"plan {plan_id!r} not found")
    result = _compile(plan.to_dict())
    if not result.get("valid"):
        raise HTTPException(status_code=422, detail={"errors": result.get("errors", [])})
    return result


@router.post("/plans/{plan_id}/execute")
async def execute_plan(plan_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """POST /plans/{plan_id}/execute — compile + run the ExecutionGraph."""
    from common_lib.modules.decision_engine.approval import service as approval
    from common_lib.modules.decision_engine.execution.compiler import compile_plan as _compile
    from common_lib.modules.decision_engine.execution.runtime import execute_graph as _run

    _require_fabric()
    plan = approval.GLOBAL_REGISTRY.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"plan {plan_id!r} not found")
    compiled = _compile(plan.to_dict())
    if not compiled.get("valid"):
        raise HTTPException(status_code=422, detail={"errors": compiled.get("errors", [])})
    body = payload or {}
    handlers = body.get("tool_handlers") or {}
    run = _run(
        compiled["graph"],
        tool_handlers=handlers,  # host-supplied handlers only; never raw plans
        max_steps=body.get("max_steps"),
    )
    return run


@router.post("/plans/{plan_id}/replan")
async def replan_plan(plan_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """POST /plans/{plan_id}/replan — §91: pause → new version → re-review."""
    from common_lib.modules.decision_engine.approval.service import review_plan

    _require_fabric()
    body = payload or {}
    result = review_plan(
        plan_id,
        "edit",
        reviewer=str(body.get("reviewer", "system")),
        comments=str(body.get("reason", "replan requested")),
        changes=[{"op": "replan", **(body.get("changes") or {})}],
    )
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("error", "replan failed"))
    return result


# ── DF-056 coordination endpoints (thin) ─────────────────────────────────


@router.post("/coordination/intake")
async def coordination_intake(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST /coordination/intake — record a requirement (flag-guarded)."""
    _require_coordination()
    from common_lib.modules.decision_engine.coordination.requirement import record_requirement
    result = record_requirement(
        raw_text=str(payload.get("raw_text", "")),
        goal=str(payload.get("goal", "")),
        success_criteria=list(payload.get("success_criteria") or []),
        constraints=list(payload.get("constraints") or []),
        requester=str(payload.get("requester", "api")),
        priority=str(payload.get("priority", "normal")),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail={"errors": result.get("errors", [])})
    return result


@router.post("/coordination/run")
async def coordination_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST /coordination/run — full pipeline: gate → decompose → DAG → assign."""
    _require_coordination()
    from common_lib.modules.decision_engine.coordination.coordinator import run_coordination

    result = run_coordination(
        dict(payload.get("requirement") or {}),
        skills=list(payload.get("skills") or []) or None,
        capabilities=list(payload.get("capabilities") or []) or None,
    )
    if result.get("state") == "BLOCKED" and "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    return result


@router.post("/coordination/assign")
async def coordination_assign(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST /coordination/assign — assign tasks to skills/capabilities."""
    _require_coordination()
    from common_lib.modules.decision_engine.coordination.assigner import assign_tasks
    return assign_tasks(
        tasks=list(payload.get("tasks") or []),
        skills=list(payload.get("skills") or []) or None,
        capabilities=list(payload.get("capabilities") or []) or None,
    )


@router.post("/coordination/schedule")
async def coordination_schedule(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST /coordination/schedule — 3-mode schedule over the task DAG."""
    _require_coordination()
    from common_lib.modules.decision_engine.coordination.estimators import estimate_tasks
    from common_lib.modules.decision_engine.coordination.schedules import (
        schedule_cheapest,
        schedule_custom,
        schedule_fastest,
    )
    from common_lib.modules.decision_engine.coordination.task_graph import build_task_dag

    mode = str(payload.get("mode", "fastest")).lower()
    tasks = list(payload.get("tasks") or [])
    edges = [
        {"from": str(e.get("from", "")), "to": str(e.get("to", ""))}
        for e in (payload.get("dependencies") or payload.get("edges") or [])
    ]
    try:
        dag = build_task_dag(tasks, edges)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    estimates = estimate_tasks(tasks, capabilities=list(payload.get("capabilities") or []) or None)
    if mode == "cheapest":
        return schedule_cheapest(dag, estimates)
    if mode == "custom":
        try:
            return schedule_custom(
                dag,
                estimates,
                serial=[list(p) for p in (payload.get("serial") or [])],
                parallel=[list(p) for p in (payload.get("parallel") or [])],
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    return schedule_fastest(dag, estimates)


@router.post("/coordination/artefacts")
async def coordination_artefacts(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST /coordination/artefacts — emit the versioned artefact bundle."""
    _require_coordination()
    from common_lib.modules.decision_engine.coordination.artefacts import emit_artefact_bundle
    try:
        return emit_artefact_bundle(
            dict(payload.get("run_report") or {}),
            schedules=dict(payload.get("schedules") or {}) or None,
            qa_log=list(payload.get("qa_log") or []) or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/coordination/checkpoints")
async def coordination_checkpoints(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST /coordination/checkpoints — aggregate task results (merge)."""
    _require_coordination()
    from common_lib.modules.decision_engine.coordination.aggregator import aggregate_results
    return aggregate_results(
        bundle=dict(payload.get("bundle") or {}),
        results=list(payload.get("results") or []),
    )
