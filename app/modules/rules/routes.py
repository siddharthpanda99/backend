"""
Unified Rules Router

Thin FastAPI router for the unified rules engine definitions.
All CRUD + evaluate endpoints.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from common_lib.modules.data_storage.database.connection import get_session

router = APIRouter(prefix="/rules", tags=["Unified Rules"])


# ── Pydantic Schemas ────────────────────────────────────────────────


class RuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rule_type: str = "threshold"
    conditions: Optional[Dict[str, Any]] = None
    scope: str = "pipeline"
    target_type: str = "hook"
    target_id: Optional[str] = None
    enabled: bool = True
    priority: int = 100
    tags: list[str] = []


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    scope: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    tags: Optional[list[str]] = None


class RuleEvaluateRequest(BaseModel):
    input_data: Dict[str, Any] = {}


# ── Note: Rules use InterceptorDefinitionDB with a 'rule' convention ──
# For simplicity, we store rules in the interceptor_definitions table
# with a distinguishing prefix in the name, or use a separate table.
# Here we use a lightweight dict-based approach since the rules engine
# already has its own persistence in governance.

# We'll create a simple in-memory store for rules, backed by a JSON file.
# In production, this should be a proper DB table.

_rules_store: Dict[int, dict] = {}
_rule_counter = 0


def _rule_to_dict(rule: dict) -> dict:
    return rule


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("")
def list_rules(
    scope: Optional[str] = None,
    rule_type: Optional[str] = None,
):
    items = list(_rules_store.values())
    if scope:
        items = [r for r in items if r.get("scope") == scope]
    if rule_type:
        items = [r for r in items if r.get("rule_type") == rule_type]
    return items


@router.post("")
def create_rule(body: RuleCreate):
    global _rule_counter
    _rule_counter += 1
    now = datetime.utcnow().isoformat()
    rule = {
        "id": _rule_counter,
        "name": body.name,
        "description": body.description,
        "rule_type": body.rule_type,
        "conditions": body.conditions or {},
        "scope": body.scope,
        "target_type": body.target_type,
        "target_id": body.target_id,
        "enabled": body.enabled,
        "priority": body.priority,
        "tags": body.tags,
        "created_at": now,
        "updated_at": now,
    }
    _rules_store[_rule_counter] = rule
    return rule


@router.get("/{rule_id}")
def get_rule(rule_id: int):
    rule = _rules_store.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.put("/{rule_id}")
def update_rule(rule_id: int, body: RuleUpdate):
    rule = _rules_store.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    update_data = body.model_dump(exclude_unset=True)
    rule.update(update_data)
    rule["updated_at"] = datetime.utcnow().isoformat()
    return rule


@router.delete("/{rule_id}")
def delete_rule(rule_id: int):
    if rule_id not in _rules_store:
        raise HTTPException(status_code=404, detail="Rule not found")
    del _rules_store[rule_id]
    return {"status": "deleted"}


@router.post("/{rule_id}/evaluate")
def evaluate_rule(rule_id: int, body: RuleEvaluateRequest):
    """Evaluate a rule with mock input data."""
    rule = _rules_store.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    # TODO: Integrate with the actual rules engine
    conditions = rule.get("conditions", {})
    input_data = body.input_data
    # Simple threshold evaluation stub
    result = {
        "rule_id": rule_id,
        "rule_name": rule["name"],
        "input": input_data,
        "conditions": conditions,
        "matched": True,  # Stub
        "message": "Rule evaluation stub — integrate with rules_engine",
    }
    return result
