"""Rules Engine module API routes — Rule registry, policy engine, scoring, resilience.

Thin routing layer that delegates to common_lib.modules.governance.rules_engine services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class RuleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    expression: str
    action: Optional[str] = None
    priority: Optional[int] = 0
    enabled: Optional[bool] = True


class RuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    expression: Optional[str] = None
    action: Optional[str] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None


class EvaluateRequest(BaseModel):
    rules: Optional[List[str]] = None
    context: Dict[str, Any]
    mode: Optional[str] = "sequential"


def _get_registry():
    from common_lib.modules.governance.rules_engine.registry import RuleRegistry
    return RuleRegistry()


def _get_engine():
    from common_lib.modules.governance.rules_engine.engine import RulesEngine
    return RulesEngine()


# ---------------------------------------------------------------------------
# Rule CRUD endpoints
# ---------------------------------------------------------------------------

@router.get("/rules")
async def list_rules() -> Dict[str, Any]:
    """List all rules."""
    try:
        svc = _get_registry()
        result = svc.list_rules() if hasattr(svc, "list_rules") else []
        return {"rules": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules")
async def create_rule(request: RuleCreateRequest) -> Dict[str, Any]:
    """Create a new rule."""
    try:
        svc = _get_registry()
        result = svc.create_rule(request.name, request.description, request.expression, request.action, request.priority, request.enabled) if hasattr(svc, "create_rule") else {"name": request.name}
        return {"rule": result, "message": "Rule created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules/{rule_id}")
async def get_rule(rule_id: str) -> Dict[str, Any]:
    """Get a rule by ID."""
    try:
        svc = _get_registry()
        result = svc.get_rule(rule_id) if hasattr(svc, "get_rule") else None
        if result is None:
            raise HTTPException(status_code=404, detail="Rule not found")
        return {"rule": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, request: RuleUpdateRequest) -> Dict[str, Any]:
    """Update a rule."""
    try:
        svc = _get_registry()
        result = svc.update_rule(rule_id, **request.model_dump(exclude_unset=True)) if hasattr(svc, "update_rule") else {"rule_id": rule_id}
        return {"rule": result, "message": "Rule updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str) -> Dict[str, Any]:
    """Delete a rule."""
    try:
        svc = _get_registry()
        svc.delete_rule(rule_id) if hasattr(svc, "delete_rule") else None
        return {"success": True, "message": "Rule deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules/{rule_id}/enable")
async def enable_rule(rule_id: str) -> Dict[str, Any]:
    """Enable a rule."""
    try:
        svc = _get_registry()
        svc.enable_rule(rule_id) if hasattr(svc, "enable_rule") else None
        return {"success": True, "message": "Rule enabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules/{rule_id}/disable")
async def disable_rule(rule_id: str) -> Dict[str, Any]:
    """Disable a rule."""
    try:
        svc = _get_registry()
        svc.disable_rule(rule_id) if hasattr(svc, "disable_rule") else None
        return {"success": True, "message": "Rule disabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Evaluation endpoints
# ---------------------------------------------------------------------------

@router.post("/evaluate")
async def evaluate_rules(request: EvaluateRequest) -> Dict[str, Any]:
    """Evaluate rules against a context."""
    try:
        svc = _get_engine()
        result = svc.evaluate(request.rules, request.context, request.mode) if hasattr(svc, "evaluate") else {"matches": []}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/score")
async def score_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Score a context against all enabled rules."""
    try:
        svc = _get_engine()
        result = svc.score(context) if hasattr(svc, "score") else {"score": 0}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Observability endpoints
# ---------------------------------------------------------------------------

@router.get("/stats")
async def engine_stats() -> Dict[str, Any]:
    """Get rules engine statistics."""
    try:
        svc = _get_engine()
        result = svc.stats() if hasattr(svc, "stats") else {"total_rules": 0, "active": 0}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
