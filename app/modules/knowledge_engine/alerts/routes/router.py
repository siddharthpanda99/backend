"""``app.modules.knowledge_engine.alerts.routes.router`` — FastAPI routes for Alerts module.

Thin router layer that delegates to AlertManager service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.alerts.errors import (
    ConflictError,
    FeatureDisabledError,
    InvalidArgumentError,
    ResourceNotFoundError,
)
from common_lib.modules.knowledge_engine.alerts.schemas import (
    AlertChannel,
    AlertRuleCreate,
    AlertRuleUpdate,
    EvaluateRequest,
)
from common_lib.modules.knowledge_engine.alerts.service import AlertManager

router = APIRouter(prefix="/alerts", tags=["alerts"])

_SERVICE: AlertManager | None = None


def _get_service() -> AlertManager:
    """Process-wide AlertManager singleton."""
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = AlertManager()
    return _SERVICE


# ── Request/Response Models ───────────────────────────────────────


class AlertRuleCreateRequest(BaseModel):
    kb_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(default="", max_length=1024)
    trigger: str = Field(
        ...,
        pattern="^(fact_changed|fact_conflict|new_ontology_miss|sync_failure|entity_merge_review)$",
    )
    condition: dict[str, Any] = Field(default_factory=dict)
    severity: str = Field(default="info", pattern="^(info|warning|critical)$")
    cooldown_seconds: int = Field(default=3600, ge=1)
    channels: list[AlertChannel] = Field(default_factory=list)
    created_by: str = Field(default="system", max_length=128)


class AlertRuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    condition: dict[str, Any] | None = None
    severity: str | None = Field(default=None, pattern="^(info|warning|critical)$")
    cooldown_seconds: int | None = Field(default=None, ge=1)
    channels: list[AlertChannel] | None = None
    enabled: bool | None = None


class EvaluateRequestModel(BaseModel):
    kb_id: str = Field(..., min_length=1)
    trigger: str = Field(
        ...,
        pattern="^(fact_changed|fact_conflict|new_ontology_miss|sync_failure|entity_merge_review)$",
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    entity_id: str | None = None
    fact_id: str | None = None


class AcknowledgeRequest(BaseModel):
    alert_id: str
    acknowledged_by: str = Field(default="system")


class ResolveRequest(BaseModel):
    alert_id: str
    resolved_by: str = Field(default="system")


class DispatchRequest(BaseModel):
    alert_id: str


# ── Helpers ───────────────────────────────────────────────────────


def _handle_service_error(exc: Exception) -> HTTPException:
    """Convert service exceptions to HTTP exceptions."""
    if isinstance(exc, FeatureDisabledError):
        return HTTPException(status_code=503, detail=exc.message)
    if isinstance(exc, InvalidArgumentError):
        return HTTPException(status_code=400, detail=exc.message)
    if isinstance(exc, ResourceNotFoundError):
        return HTTPException(status_code=404, detail=exc.message)
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=409, detail=exc.message)
    return HTTPException(status_code=500, detail=str(exc))


# ── AlertRule CRUD ────────────────────────────────────────────────


@router.post("/rules", response_model=dict[str, Any])
async def create_rule(request: AlertRuleCreateRequest):
    """Create a new alert rule."""
    try:
        return _get_service().create_rule(
            kb_id=request.kb_id,
            name=request.name,
            trigger=request.trigger,
            description=request.description,
            condition=request.condition,
            severity=request.severity,
            cooldown_seconds=request.cooldown_seconds,
            channels=[ch.model_dump() for ch in request.channels],
            created_by=request.created_by,
        )
    except Exception as exc:
        raise _handle_service_error(exc)


@router.get("/rules/{rule_id}", response_model=dict[str, Any])
async def get_rule(kb_id: str = Query(...), rule_id: str = ...):
    """Get an alert rule by ID."""
    try:
        return _get_service().get_rule(kb_id, rule_id)
    except Exception as exc:
        raise _handle_service_error(exc)


@router.get("/rules", response_model=dict[str, Any])
async def list_rules(
    kb_id: str = Query(...),
    trigger: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List alert rules for a KB with optional filters."""
    try:
        return _get_service().list_rules(
            kb_id, trigger=trigger, enabled=enabled, limit=limit, offset=offset
        )
    except Exception as exc:
        raise _handle_service_error(exc)


@router.patch("/rules/{rule_id}", response_model=dict[str, Any])
async def update_rule(
    kb_id: str = Query(...),
    rule_id: str = ...,
    request: AlertRuleUpdateRequest = ...,
):
    """Update an alert rule."""
    try:
        return _get_service().update_rule(
            kb_id,
            rule_id,
            name=request.name,
            description=request.description,
            condition=request.condition,
            severity=request.severity,
            cooldown_seconds=request.cooldown_seconds,
            channels=[ch.model_dump() for ch in request.channels]
            if request.channels
            else None,
            enabled=request.enabled,
        )
    except Exception as exc:
        raise _handle_service_error(exc)


@router.delete("/rules/{rule_id}", response_model=dict[str, Any])
async def delete_rule(kb_id: str = Query(...), rule_id: str = ...):
    """Delete an alert rule."""
    try:
        return _get_service().delete_rule(kb_id, rule_id)
    except Exception as exc:
        raise _handle_service_error(exc)


# ── Alert CRUD ────────────────────────────────────────────────────


@router.get("/alerts/{alert_id}", response_model=dict[str, Any])
async def get_alert(kb_id: str = Query(...), alert_id: str = ...):
    """Get an alert by ID."""
    try:
        return _get_service().get_alert(kb_id, alert_id)
    except Exception as exc:
        raise _handle_service_error(exc)


@router.get("/alerts", response_model=dict[str, Any])
async def list_alerts(
    kb_id: str = Query(...),
    rule_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    fact_id: str | None = Query(default=None),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List alerts with filters."""
    try:
        since_dt = datetime.fromisoformat(since) if since else None
        until_dt = datetime.fromisoformat(until) if until else None
        return _get_service().list_alerts(
            kb_id,
            rule_id=rule_id,
            status=status,
            entity_id=entity_id,
            fact_id=fact_id,
            since=since_dt,
            until=until_dt,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise _handle_service_error(exc)


@router.post("/alerts/{alert_id}/acknowledge", response_model=dict[str, Any])
async def acknowledge_alert(
    kb_id: str = Query(...),
    alert_id: str = ...,
    request: AcknowledgeRequest = ...,
):
    """Acknowledge an alert."""
    try:
        return _get_service().acknowledge_alert(
            kb_id, alert_id, request.acknowledged_by
        )
    except Exception as exc:
        raise _handle_service_error(exc)


@router.post("/alerts/{alert_id}/resolve", response_model=dict[str, Any])
async def resolve_alert(
    kb_id: str = Query(...),
    alert_id: str = ...,
    request: ResolveRequest = ...,
):
    """Resolve an alert."""
    try:
        return _get_service().resolve_alert(kb_id, alert_id, request.resolved_by)
    except Exception as exc:
        raise _handle_service_error(exc)


@router.post("/alerts/{alert_id}/dismiss", response_model=dict[str, Any])
async def dismiss_alert(kb_id: str = Query(...), alert_id: str = ...):
    """Dismiss an alert."""
    try:
        return _get_service().dismiss_alert(kb_id, alert_id)
    except Exception as exc:
        raise _handle_service_error(exc)


@router.post("/alerts/{alert_id}/dispatch", response_model=dict[str, Any])
async def dispatch_alert(
    kb_id: str = Query(...),
    alert_id: str = ...,
    request: DispatchRequest = ...,
):
    """Manually dispatch a specific alert (retry failed dispatch)."""
    try:
        return _get_service().dispatch_alert(kb_id, alert_id)
    except Exception as exc:
        raise _handle_service_error(exc)


# ── Evaluation ────────────────────────────────────────────────────


@router.post("/evaluate", response_model=dict[str, Any])
async def evaluate(request: EvaluateRequestModel):
    """Evaluate all rules matching a trigger and fire alerts."""
    try:
        return _get_service().evaluate(
            kb_id=request.kb_id,
            trigger=request.trigger,
            payload=request.payload,
            entity_id=request.entity_id,
            fact_id=request.fact_id,
        )
    except Exception as exc:
        raise _handle_service_error(exc)
