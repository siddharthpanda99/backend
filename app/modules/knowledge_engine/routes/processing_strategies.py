"""
Knowledge Engine — Processing Strategy Routes.

Thin transport for the Knowledge Processing Strategies (KPS) surface. All
business logic lives in
``common_lib.modules.knowledge_engine.processing_strategy.service.ProcessingStrategyService``;
this module only translates HTTP <-> service calls (G1).

Every endpoint the KnowledgebasePage "Processing Strategies" tab calls is
declared here. Before this router existed the tab called
``/api/v1/processing-strategies*``, which had no backend implementation at
all — see the module audit report
(``docs/duplication-audit/MODULE-AUDIT-knowledge_engine.md``, C2/C4).

The whole surface is gated by the ``KPS_ENABLED`` feature flag, which the
service itself enforces via ``_check_enabled()``. When the flag is off every
route returns 503 rather than a misleading 404/500, so the UI can tell
"feature disabled" from "endpoint missing".
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.processing_strategy.feature_flags import (
    KPS_ENABLED,
)
from common_lib.modules.knowledge_engine.processing_strategy.service import (
    get_processing_strategy_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/processing-strategies", tags=["Knowledge Engine — Processing Strategies"]
)


# ── Dependency Injection ─────────────────────────────────────────────


def get_service() -> Any:
    """Return the processing-strategy service singleton."""
    return get_processing_strategy_service()


def _require_enabled() -> None:
    """503 when the KPS feature flag is off (distinct from 'not found')."""
    if not KPS_ENABLED.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Knowledge Processing Strategies are disabled "
                "(KPS_ENABLED feature flag is off)."
            ),
        )


# ── Request Models ───────────────────────────────────────────────────


class CreateStrategyRequest(BaseModel):
    kb_id: str
    name: str
    applies_to: dict[str, Any] = Field(default_factory=dict)
    pipeline_config: dict[str, Any] = Field(default_factory=dict)
    created_by: str = "api"
    description: str = ""
    tags: list[str] | None = None


class UpdateStrategyRequest(BaseModel):
    changed_by: str
    change_summary: str
    name: str | None = None
    applies_to: dict[str, Any] | None = None
    pipeline_config: dict[str, Any] | None = None
    description: str | None = None
    tags: list[str] | None = None


class ActorRequest(BaseModel):
    """Single-actor body used by the activate/approve endpoints."""

    requested_by: str | None = None
    approved_by: str | None = None


class MatchStrategyRequest(BaseModel):
    kb_id: str
    profile: dict[str, Any] = Field(default_factory=dict)


class AssignmentRequest(BaseModel):
    kb_id: str
    strategy_id: str
    assigned_by: str = "api"
    strategy_version: int = 1
    source_id: str | None = None
    connector_type: str | None = None
    priority: int = 100


class ExecutionRequest(BaseModel):
    """Telemetry write payload (see ProcessingStrategyService.record_execution)."""

    kb_id: str
    job_id: str
    strategy_id: str
    strategy_version: int
    actual_profile: dict[str, Any] = Field(default_factory=dict)
    status: str
    stages_completed: list[str] = Field(default_factory=list)
    chunks_produced: int = 0
    entities_extracted: int = 0
    facts_extracted: int = 0
    drop_signal_count: int = 0
    extraction_confidence_avg: float | None = None
    validation_pass_rate: float | None = None
    llm_tokens_in: int = 0
    llm_tokens_out: int = 0
    embedding_tokens: int = 0
    estimated_cost_usd: float = 0.0
    duration_ms: int | None = None
    error_message: str | None = None


# ── Routes ───────────────────────────────────────────────────────────


@router.get("")
async def list_strategies(
    kb_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service=Depends(get_service),
):
    """List processing strategies with optional filters."""
    _require_enabled()
    try:
        return service.list_strategies(
            kb_id=kb_id, status=status, limit=limit, offset=offset
        )
    except Exception as exc:
        logger.exception("list_strategies failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to list strategies: {exc}"
        ) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_strategy(request: CreateStrategyRequest, service=Depends(get_service)):
    """Create a new processing strategy (draft)."""
    _require_enabled()
    try:
        return service.create_strategy(
            kb_id=request.kb_id,
            name=request.name,
            applies_to=request.applies_to,
            pipeline_config=request.pipeline_config,
            created_by=request.created_by,
            description=request.description,
            tags=request.tags,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("create_strategy failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to create strategy: {exc}"
        ) from exc


@router.post("/match")
async def match_strategy(request: MatchStrategyRequest, service=Depends(get_service)):
    """Match a document profile against the registered strategies."""
    _require_enabled()
    try:
        return service.match_strategy(request.kb_id, request.profile)
    except Exception as exc:
        logger.exception("match_strategy failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to match strategy: {exc}"
        ) from exc


@router.get("/assignments")
async def list_assignments(kb_id: str = Query(...), service=Depends(get_service)):
    """List strategy assignments for a knowledge base."""
    _require_enabled()
    try:
        return service.list_assignments(kb_id)
    except Exception as exc:
        logger.exception("list_assignments failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to list assignments: {exc}"
        ) from exc


@router.post("/assign")
async def assign_strategy(request: AssignmentRequest, service=Depends(get_service)):
    """Assign a strategy to a knowledge base / source."""
    _require_enabled()
    try:
        return service.assign_strategy(
            kb_id=request.kb_id,
            strategy_id=request.strategy_id,
            assigned_by=request.assigned_by,
            strategy_version=request.strategy_version,
            source_id=request.source_id,
            connector_type=request.connector_type,
            priority=request.priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("assign_strategy failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to assign strategy: {exc}"
        ) from exc


@router.post("/executions")
async def record_execution(request: ExecutionRequest, service=Depends(get_service)):
    """Record a strategy execution for telemetry."""
    _require_enabled()
    try:
        return service.record_execution(**request.model_dump())
    except Exception as exc:
        logger.exception("record_execution failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to record execution: {exc}"
        ) from exc


@router.get("/{strategy_id}")
async def get_strategy(
    strategy_id: str,
    include_versions: bool = Query(default=True),
    service=Depends(get_service),
):
    """Get a processing strategy by ID, optionally with version history."""
    _require_enabled()
    try:
        result = service.get_strategy(strategy_id, include_versions)
        if result is None:
            raise HTTPException(
                status_code=404, detail=f"Strategy {strategy_id} not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get_strategy failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to get strategy: {exc}"
        ) from exc


@router.patch("/{strategy_id}")
async def update_strategy(
    strategy_id: str, request: UpdateStrategyRequest, service=Depends(get_service)
):
    """Update a strategy (creates a new version)."""
    _require_enabled()
    try:
        result = service.update_strategy(
            strategy_id=strategy_id,
            changed_by=request.changed_by,
            change_summary=request.change_summary,
            name=request.name,
            applies_to=request.applies_to,
            pipeline_config=request.pipeline_config,
            description=request.description,
            tags=request.tags,
        )
        if result is None:
            raise HTTPException(
                status_code=404, detail=f"Strategy {strategy_id} not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("update_strategy failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to update strategy: {exc}"
        ) from exc


@router.post("/{strategy_id}/activate")
async def activate_strategy(
    strategy_id: str, request: ActorRequest, service=Depends(get_service)
):
    """Submit a draft strategy for approval (draft -> active)."""
    _require_enabled()
    try:
        result = service.activate_strategy(strategy_id, request.requested_by or "api")
        if result is None:
            raise HTTPException(
                status_code=404, detail=f"Strategy {strategy_id} not found"
            )
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("activate_strategy failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to activate strategy: {exc}"
        ) from exc


@router.post("/{strategy_id}/approve")
async def approve_strategy(
    strategy_id: str, request: ActorRequest, service=Depends(get_service)
):
    """Approve an active strategy (admin action)."""
    _require_enabled()
    try:
        result = service.approve_strategy(strategy_id, request.approved_by or "api")
        if result is None:
            raise HTTPException(
                status_code=404, detail=f"Strategy {strategy_id} not found"
            )
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("approve_strategy failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to approve strategy: {exc}"
        ) from exc


@router.post("/{strategy_id}/deprecate")
async def deprecate_strategy(strategy_id: str, service=Depends(get_service)):
    """Deprecate a strategy (active -> deprecated)."""
    _require_enabled()
    try:
        result = service.deprecate_strategy(strategy_id)
        if result is None:
            raise HTTPException(
                status_code=404, detail=f"Strategy {strategy_id} not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("deprecate_strategy failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to deprecate strategy: {exc}"
        ) from exc


@router.get("/{strategy_id}/telemetry")
async def get_telemetry(
    strategy_id: str,
    days: int = Query(default=30, ge=1, le=365),
    service=Depends(get_service),
):
    """Get telemetry metrics for a strategy over a lookback window."""
    _require_enabled()
    try:
        return service.get_telemetry(strategy_id, days)
    except Exception as exc:
        logger.exception("get_telemetry failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to get telemetry: {exc}"
        ) from exc


__all__ = ["router"]
