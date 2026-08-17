"""Toolchain Builder — REST API routes.

Mounted at ``/api/v1/toolchain``. Thin-router convention: all logic lives in
``common_lib.modules.orchestration.toolchain``.

Used by the Toolchain Visualizer UI to show *how* a query would be routed
(workflow → tool → system → multi-agent decomposition) before executing it,
plus a dry-run of the resulting plan.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


def _router() -> Any:
    from common_lib.modules.orchestration.toolchain.router import ToolchainRouter

    return ToolchainRouter()


def _builder() -> Any:
    from common_lib.modules.orchestration.toolchain.builder import ToolchainBuilder

    return ToolchainBuilder()


class RouteRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
    context: Optional[Dict[str, Any]] = None


class PlanRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
    context: Optional[Dict[str, Any]] = None
    execute: Optional[bool] = False


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/route", tags=["Toolchain"])
async def route_query(req: RouteRequest) -> Dict[str, Any]:
    """Dry-run: how would this query be routed? (workflow/tool/system/agent)

    Returns the routing decision only — nothing is executed. The UI renders
    this as the decision chain of the Toolchain Visualizer.
    """
    try:
        decision = await _router().route(req.query, context=req.context or {})
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("toolchain route failed")
        raise HTTPException(status_code=500, detail=f"Routing failed: {exc}")
    return {
        "query": req.query,
        "decision": decision.model_dump(mode="json"),
    }


@router.post("/plan", tags=["Toolchain"])
async def build_plan(req: PlanRequest) -> Dict[str, Any]:
    """Full plan: route the query, then produce the task plan (no execution).

    ``execute=true`` runs the plan through the ToolchainBuilder and returns
    the full execution trace.
    """
    try:
        if req.execute:
            result = await _builder().execute(
                req.query, context=req.context or {}
            )
            return {
                "query": req.query,
                "executed": True,
                "coordination_id": result.coordination_id,
                "decision": (
                    result.decision.model_dump(mode="json")
                    if result.decision
                    else None
                ),
                "plan": (
                    result.plan.model_dump(mode="json") if result.plan else None
                ),
                "tasks": [
                    t.model_dump(mode="json") for t in (result.tasks or [])
                ],
                "final_result": result.final_result,
                "trace": [t.model_dump(mode="json") for t in (result.trace or [])],
                "duration_ms": result.duration_ms,
                "errors": result.errors,
            }
        # Dry-run: route + plan only.
        decision = await _router().route(req.query, context=req.context or {})
        plan = await _builder().plan(req.query, decision=decision, context=req.context or {})
        return {
            "query": req.query,
            "executed": False,
            "decision": decision.model_dump(mode="json"),
            "plan": plan.model_dump(mode="json") if plan else None,
        }
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("toolchain plan failed")
        raise HTTPException(status_code=500, detail=f"Planning failed: {exc}")


@router.get("/trace/{coordination_id}", tags=["Toolchain"])
async def get_trace(coordination_id: str) -> Dict[str, Any]:
    """Fetch a persisted toolchain execution trace by coordination id."""
    try:
        from common_lib.modules.orchestration.toolchain.tracing import (
            ToolchainTracing,
        )

        trace = ToolchainTracing().get_trace(coordination_id)
        if trace is None:
            raise HTTPException(
                status_code=404, detail=f"Trace {coordination_id} not found"
            )
        return {"coordination_id": coordination_id, "trace": trace}
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("toolchain trace fetch failed")
        raise HTTPException(status_code=500, detail=f"Trace fetch failed: {exc}")
