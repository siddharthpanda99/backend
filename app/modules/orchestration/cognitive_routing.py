"""Cognitive routing — thin router (COGR Phase 4.1).

All logic lives in common_lib.modules.orchestration.routing.*.
Endpoints:
- POST /orchestration/cognitive/route        → route(capability, context, constraints)
- GET  /orchestration/cognitive/strategies    → list of 5 strategies
- POST /orchestration/cognitive/plan          → build_plan(strategy, ...)
- POST /orchestration/cognitive/fallback      → resolve_fallback(...)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cognitive", tags=["Cognitive Routing"])


@router.post("/route")
async def cognitive_route(body: Dict[str, Any]) -> Dict[str, Any]:
    """Select the best model for a capability (policy-first, then scored)."""
    try:
        from common_lib.modules.orchestration.routing.decision_function import route

        decision = route(
            str(body.get("capability", "chat")),
            dict(body.get("context") or {}),
            dict(body.get("constraints") or {}),
        )
        sel = decision.selected
        run = decision.runner_up
        return {
            "capability": decision.capability,
            "selected": (
                sel.model_dump()
                if hasattr(sel, "model_dump")
                else (dict(sel) if isinstance(sel, dict) else None)
            )
            if sel
            else None,
            "runner_up": (
                run.model_dump()
                if hasattr(run, "model_dump")
                else (dict(run) if isinstance(run, dict) else None)
            )
            if run
            else None,
            "reasons": decision.reasons,
            "scores": decision.scores,
            "denied": decision.denied,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("cognitive.route failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/strategies")
async def cognitive_strategies() -> Dict[str, Any]:
    """List the 5 routing strategies."""
    try:
        from common_lib.modules.orchestration.routing.strategies import STRATEGIES

        return {"strategies": sorted(STRATEGIES)}
    except Exception as exc:  # noqa: BLE001
        logger.error("cognitive.strategies failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/plan")
async def cognitive_plan(body: Dict[str, Any]) -> Dict[str, Any]:
    """Build an ordered invocation plan for a strategy."""
    try:
        from common_lib.modules.orchestration.routing.strategies import build_plan

        plan = build_plan(
            str(body.get("strategy", "direct")),
            str(body.get("capability", "chat")),
            list(body.get("eligible") or []),
            dict(body.get("context") or {}),
        )
        steps: List[Dict[str, Any]] = []
        for s in plan.steps:
            if hasattr(s, "model_id"):
                steps.append(
                    {"model_id": s.model_id, "role": s.role, "params": dict(s.params)}
                )
            elif isinstance(s, dict):
                steps.append(dict(s))
        return {
            "strategy": plan.strategy,
            "steps": steps,
            "aggregator": plan.aggregator,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("cognitive.plan failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/fallback")
async def cognitive_fallback(body: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the next eligible model after a failure."""
    try:
        from common_lib.modules.orchestration.routing.fallback import resolve_fallback

        return dict(
            resolve_fallback(
                str(body.get("capability", "chat")),
                str(body.get("failed_model", "")),
                str(body.get("data_class", "public")),
                list(body.get("candidates") or None)
                if body.get("candidates")
                else None,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("cognitive.fallback failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/policies/apply")
async def cognitive_apply_policies(body: Dict[str, Any]) -> Dict[str, Any]:
    """Apply risk/privacy/cost/execution-mode constraints to candidates."""
    try:
        from common_lib.modules.orchestration.nodes.cognitive_routing import (
            cogr_apply_routing_policies,
        )

        return dict(
            cogr_apply_routing_policies(
                candidate_ids=list(body.get("candidate_ids") or []),
                risk_level=str(body.get("risk_level", "R0")),
                data_class=str(body.get("data_class", "public")),
                execution_mode=str(body.get("execution_mode", "hybrid")),
                max_cost=body.get("max_cost"),
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("cognitive.policies failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
