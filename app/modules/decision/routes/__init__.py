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
    from common_lib.modules.decision_engine.contracts import (
        DecisionEdge,
        DecisionNode,
        DecisionPlan,
        RiskModel,
    )

    # Carry the full graph through: the builder canvas sends nodes/edges and
    # the execution policy, and the validator (§81) needs the policy to pass
    # rule 13. Dropping them here made every builder plan invalid.
    try:
        nodes = [DecisionNode.from_dict(n) for n in payload.get("nodes") or []]
        edges = [DecisionEdge.from_dict(e) for e in payload.get("edges") or []]
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid nodes/edges: {exc}")

    plan = DecisionPlan(
        plan_id=plan_id,
        goal=goal,
        status=status,
        assumptions=list(payload.get("assumptions") or []),
        unknowns=list(payload.get("unknowns") or []),
        constraints=list(payload.get("constraints") or []),
        evidence_requirements=list(payload.get("evidence_requirements") or []),
        decisions=list(payload.get("decisions") or []),
        nodes=nodes,
        edges=edges,
        execution_policy=dict(payload.get("execution_policy") or {}),
        risk=RiskModel(**(payload.get("risk") or {})),
    )
    approval.create_plan_version(
        plan.to_dict(), author=str(payload.get("requester", "api"))
    )
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
async def approve_plan(
    plan_id: str, payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
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
        raise HTTPException(
            status_code=409, detail=result.get("error", "approve failed")
        )
    return result


@router.post("/plans/{plan_id}/reject")
async def reject_plan(
    plan_id: str, payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
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
        raise HTTPException(
            status_code=409, detail=result.get("error", "reject failed")
        )
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


@router.get("/executions/{execution_id}/stream")
async def stream_execution(execution_id: str) -> Any:
    """GET /executions/{id}/stream — SSE lifecycle for one execution.

    The execution runtime is synchronous, so by the time a client subscribes
    the run has already been recorded. Rather than leave the UI's EventSource
    permanently offline, this replays the stored record as the same event
    sequence the runtime emits, ending with a terminal event. Callers get the
    real outcome of the run they just triggered.
    """
    import json as _json
    import asyncio as _asyncio
    from datetime import datetime, timezone

    from fastapi.responses import StreamingResponse

    from common_lib.modules.decision_engine.telemetry import history as _history

    _require_fabric()
    record = _history.GLOBAL_EXECUTION_HISTORY.get(execution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    plan_id = str(record.get("planId", ""))
    plan_version = int(record.get("planVersion") or 0)
    executed = [str(s) for s in (record.get("executed") or [])]
    results = dict(record.get("results") or {})

    def frame(event_type: str, data: Dict[str, Any]) -> str:
        payload = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": execution_id,
            "data": data,
        }
        return f"data: {_json.dumps(payload)}\n\n"

    async def event_source():
        yield frame(
            "execution_started",
            {
                "plan_id": plan_id,
                "plan_version": plan_version,
                "execution_graph": {
                    "nodes": [{"id": s, "type": "TASK", "config": {}} for s in executed],
                    "edges": [],
                    "checkpoints": [],
                },
                "initial_context": {},
            },
        )
        for step in executed:
            yield frame("node_started", {"node_id": step, "node_type": "TASK", "attempt": 1})
            await _asyncio.sleep(0)
            yield frame(
                "node_completed",
                {
                    "node_id": step,
                    "node_type": "TASK",
                    "result": results.get(step) or {},
                    "duration_ms": 0,
                },
            )
        terminal = str(record.get("status", "COMPLETED"))
        if terminal not in ("COMPLETED", "FAILED", "INTERRUPTED"):
            terminal = "COMPLETED"
        yield frame(
            "execution_completed",
            {
                "status": terminal,
                "results": results,
                "checkpoints": {},
                "duration_ms": int(record.get("durationMs") or 0),
                **({"error": record.get("error")} if record.get("error") else {}),
            },
        )

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/plans/{plan_id}/diff")
async def diff_plan_versions(
    plan_id: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """POST /plans/{plan_id}/diff — field-level diff between two versions (§19).

    Backs the Plan Contracts diff view. ApprovalService.get_version_diff
    already computed this; it simply had no route, so the UI's request 404'd.
    """
    from common_lib.modules.decision_engine.services import ApprovalService

    _require_fabric()
    try:
        from_version = int(payload.get("from_version", 1))
        to_version = int(payload.get("to_version", 1))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422, detail="from_version and to_version must be integers"
        )

    diff = ApprovalService().get_version_diff(plan_id, from_version, to_version)
    return {
        "plan_id": plan_id,
        "from_version": from_version,
        "to_version": to_version,
        "changes": diff,
        "total": len(diff),
    }


@router.post("/plans/{plan_id}/compile")
async def compile_plan(plan_id: str) -> Dict[str, Any]:
    """POST /plans/{plan_id}/compile — approved plan → ExecutionGraph (§35)."""
    from common_lib.modules.decision_engine.approval import service as approval
    from common_lib.modules.decision_engine.execution.compiler import (
        compile_plan as _compile,
    )

    _require_fabric()
    plan = approval.GLOBAL_REGISTRY.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"plan {plan_id!r} not found")
    result = _compile(plan.to_dict())
    if not result.get("valid"):
        raise HTTPException(
            status_code=422, detail={"errors": result.get("errors", [])}
        )
    return result


@router.post("/plans/{plan_id}/execute")
async def execute_plan(
    plan_id: str, payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """POST /plans/{plan_id}/execute — compile + run the ExecutionGraph."""
    from common_lib.modules.decision_engine.approval import service as approval
    from common_lib.modules.decision_engine.execution.compiler import (
        compile_plan as _compile,
    )
    from common_lib.modules.decision_engine.execution.runtime import (
        execute_graph as _run,
    )

    _require_fabric()
    plan = approval.GLOBAL_REGISTRY.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"plan {plan_id!r} not found")
    compiled = _compile(plan.to_dict())
    if not compiled.get("valid"):
        raise HTTPException(
            status_code=422, detail={"errors": compiled.get("errors", [])}
        )
    body = payload or {}
    handlers = body.get("tool_handlers") or {}
    run = _run(
        compiled["graph"],
        tool_handlers=handlers,  # host-supplied handlers only; never raw plans
        max_steps=body.get("max_steps"),
    )
    # Record the run for the execution-history surface (§57) — best-effort,
    # never fails the run itself.
    try:
        from common_lib.modules.decision_engine.telemetry.history import (
            record_execution,
        )

        record = record_execution(
            plan_id=plan_id,
            run=run,
            plan_version=plan.version,
        )
        run["executionId"] = record["executionId"]
        run["recordedAt"] = record["recordedAt"]
    except Exception:  # noqa: BLE001 — history is best-effort
        pass
    return run


@router.post("/plans/{plan_id}/replan")
async def replan_plan(
    plan_id: str, payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
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
        raise HTTPException(
            status_code=409, detail=result.get("error", "replan failed")
        )
    return result


@router.get("/plans")
async def list_plans(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """GET /plans — list all plans with optional status filter and search."""
    from common_lib.modules.decision_engine.approval import service as approval

    _require_fabric()
    plans = approval.GLOBAL_REGISTRY.list_plans(
        status=status, search=search, limit=limit
    )
    return {"plans": plans, "total": len(plans)}


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str) -> Dict[str, Any]:
    """DELETE /plans/{plan_id} — delete a plan and all its versions."""
    from common_lib.modules.decision_engine.approval import service as approval

    _require_fabric()
    deleted = approval.GLOBAL_REGISTRY.delete_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"plan {plan_id!r} not found")
    return {"ok": True, "plan_id": plan_id}


# ── DF-056 coordination endpoints (thin) ─────────────────────────────────


# ── §57 Execution-history endpoints (thin) ─────────────────────────────


@router.get("/executions")
async def list_executions(
    plan_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """GET /executions — recorded plan runs, newest first (§57)."""
    from common_lib.modules.decision_engine.telemetry.history import (
        list_executions as _list,
    )

    _require_fabric()
    return _list(plan_id=plan_id, status=status, limit=limit)


@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str) -> Dict[str, Any]:
    """GET /executions/{execution_id} — one run incl. per-node results."""
    from common_lib.modules.decision_engine.telemetry.history import (
        get_execution as _get,
    )

    _require_fabric()
    record = _get(execution_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"execution {execution_id!r} not found"
        )
    return record


@router.post("/coordination/intake")
async def coordination_intake(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST /coordination/intake — record a requirement (flag-guarded)."""
    _require_coordination()
    from common_lib.modules.decision_engine.coordination.requirement import (
        record_requirement,
    )

    result = record_requirement(
        raw_text=str(payload.get("raw_text", "")),
        goal=str(payload.get("goal", "")),
        success_criteria=list(payload.get("success_criteria") or []),
        constraints=list(payload.get("constraints") or []),
        requester=str(payload.get("requester", "api")),
        priority=str(payload.get("priority", "normal")),
    )
    if not result.get("ok"):
        raise HTTPException(
            status_code=422, detail={"errors": result.get("errors", [])}
        )
    return result


@router.post("/coordination/run")
async def coordination_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST /coordination/run — full pipeline: gate → decompose → DAG → assign."""
    _require_coordination()
    from common_lib.modules.decision_engine.coordination.coordinator import (
        run_coordination,
    )

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
    from common_lib.modules.decision_engine.coordination.estimators import (
        estimate_tasks,
    )
    from common_lib.modules.decision_engine.coordination.schedules import (
        schedule_cheapest,
        schedule_custom,
        schedule_fastest,
    )
    from common_lib.modules.decision_engine.coordination.task_graph import (
        build_task_dag,
    )

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
    estimates = estimate_tasks(
        tasks, capabilities=list(payload.get("capabilities") or []) or None
    )
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
    from common_lib.modules.decision_engine.coordination.artefacts import (
        emit_artefact_bundle,
    )

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
    from common_lib.modules.decision_engine.coordination.aggregator import (
        aggregate_results,
    )

    return aggregate_results(
        bundle=dict(payload.get("bundle") or {}),
        results=list(payload.get("results") or []),
    )
