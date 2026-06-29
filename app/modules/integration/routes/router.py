"""Integration API Routes - Cross-module status, events, traces, and management.

Provides REST endpoints for the integration layer:
- /api/v1/integration/status - Overall integration health
- /api/v1/integration/events - Event history and routing
- /api/v1/integration/traces - Trace view across modules
- /api/v1/integration/triggers - Trigger management
- /api/v1/integration/rules - Rule management
- /api/v1/integration/hooks - Hook management
- /api/v1/integration/notifications - Notification stats
- /api/v1/integration/observability - Metrics and alerts
"""

import logging
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel

from app.modules.integration.routes.versioning import resolve_api_version, validate_version

router = APIRouter(prefix="/integration", tags=["integration"])

# Include memory instance sub-routes (deploy/teardown/list/detail)
from app.modules.integration.instance_routes import router as instance_router
router.include_router(instance_router)

logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class FireEventRequest(BaseModel):
    event_type: str
    data: Dict[str, Any] = {}
    channel: str = "global"
    priority: str = "normal"
    trace_id: Optional[str] = None


class FireEventResponse(BaseModel):
    event_type: str
    actions_taken: List[str]
    errors: List[str]
    routing_time_ms: float


# =============================================================================
# Version helpers  (imported from versioning.py)
# =============================================================================
# ``resolve_api_version`` — FastAPI dependency for version negotiation
# ``validate_version``    — version validation helper
# =============================================================================


# =============================================================================
# Health / Version Info
# =============================================================================


@router.get("/health")
async def integration_health(
    api_version: str = Depends(resolve_api_version),
):
    """Get health status and version info for all served API versions.

    Reports:
      - Overall status
      - Served OpenAPI versions and their semver mappings
      - Available endpoints for each version
      - Latest version alias
    """
    try:
        from common_lib.modules.integration.docs.api_docs import API_VERSION_MAP

        return {
            "api_version": api_version,
            "status": "ok",
            "service": "integration",
            "versions": {
                label: {
                    "version": semver,
                    "openapi_path": f"/api/v1/integration/v{label.replace('v', '')}/openapi.json"
                    if label.startswith("v")
                    else None,
                }
                for label, semver in API_VERSION_MAP.items()
            },
            "latest": "v1",
        }
    except Exception as e:
        logger.error(f"Integration health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Integration Status
# =============================================================================


@router.get("/status")
async def integration_status(
    api_version: str = Depends(resolve_api_version),
):
    """Get overall integration health across all modules."""
    try:
        from common_lib.modules.integration import (
            get_event_router,
            get_context_propagation,
            get_error_handler,
            get_lifecycle_manager,
        )
        from common_lib.modules.observability import get_observability
        from common_lib.modules.notification.controller import get_notification_service
        from common_lib.modules.triggers.integration_adapter import (
            get_trigger_integration,
        )
        from common_lib.modules.hooks.integration_adapter import get_hook_integration
        from common_lib.modules.rules_engine.integration_adapter import (
            get_rules_integration,
        )

        return {
            "api_version": api_version,
            "status": "ok",
            "timestamp": time.time(),
            "modules": {
                "event_router": get_event_router().get_stats(),
                "context_propagation": get_context_propagation().get_stats(),
                "error_handler": get_error_handler().get_stats(),
                "lifecycle_manager": get_lifecycle_manager().get_stats(),
                "observability": get_observability().get_all_metrics(),
                "notification_service": get_notification_service().get_stats(),
                "triggers": get_trigger_integration().get_stats(),
                "hooks": get_hook_integration().get_stats(),
                "rules": get_rules_integration().get_stats(),
            },
        }
    except Exception as e:
        logger.error(f"Integration status failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Event Routing
# =============================================================================


@router.post("/events/fire", response_model=FireEventResponse)
async def fire_event(request: FireEventRequest):
    """Fire an event through the integration router."""
    try:
        from common_lib.modules.integration import get_event_router
        from common_lib.modules.notification.controller import Priority

        router_obj = get_event_router()
        priority = Priority(request.priority)

        result = await router_obj.fire_event(
            event_type=request.event_type,
            data=request.data,
            channel=request.channel,
            priority=priority,
            trace_id=request.trace_id,
        )

        stats = router_obj.get_stats()

        return FireEventResponse(
            event_type=request.event_type,
            actions_taken=result.get("actions_taken", []),
            errors=result.get("errors", []),
            routing_time_ms=stats.get("avg_routing_time_ms", 0),
        )
    except Exception as e:
        logger.error(f"Fire event failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/history")
async def event_history(
    api_version: str = Depends(resolve_api_version),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get recent event routing history."""
    try:
        from common_lib.modules.integration import get_event_router

        return {
            "api_version": api_version,
            "status": "ok",
            "events": get_event_router().get_event_history(limit),
            "count": limit,
        }
    except Exception as e:
        logger.error(f"Event history failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/rules")
async def routing_rules(
    api_version: str = Depends(resolve_api_version),
):
    """Get all routing rules."""
    try:
        from common_lib.modules.integration import get_event_router

        return {
            "api_version": api_version,
            "status": "ok",
            "rules": get_event_router().get_routing_rules(),
        }
    except Exception as e:
        logger.error(f"Routing rules failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Traces
# =============================================================================


@router.get("/traces")
async def list_traces(
    api_version: str = Depends(resolve_api_version),
    limit: int = Query(50, ge=1, le=500),
):
    """Get recent traces across all modules."""
    try:
        from common_lib.modules.observability import get_observability

        return {
            "api_version": api_version,
            "status": "ok",
            "traces": get_observability().get_recent_traces(limit),
            "count": limit,
        }
    except Exception as e:
        logger.error(f"List traces failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces/{trace_id}")
async def get_trace(
    trace_id: str,
    api_version: str = Depends(resolve_api_version),
):
    """Get a specific trace with all spans."""
    try:
        from common_lib.modules.observability import get_observability

        spans = get_observability().get_trace(trace_id)
        if not spans:
            raise HTTPException(status_code=404, detail=f"Trace not found: {trace_id}")

        return {
            "api_version": api_version,
            "status": "ok",
            "trace_id": trace_id,
            "spans": spans,
            "span_count": len(spans),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get trace failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Triggers
# =============================================================================


@router.get("/triggers")
async def list_triggers(
    api_version: str = Depends(resolve_api_version),
    trigger_type: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
):
    """List all triggers."""
    try:
        from common_lib.modules.triggers import (
            get_trigger_manager,
            TriggerType,
            TriggerState,
        )

        manager = get_trigger_manager()
        t_type = TriggerType(trigger_type) if trigger_type else None
        t_state = TriggerState(state) if state else None

        triggers = manager.list(trigger_type=t_type, state=t_state)

        return {
            "api_version": api_version,
            "status": "ok",
            "triggers": [
                {
                    "id": t.id,
                    "name": t.name,
                    "type": t.type.value,
                    "state": t.state.value,
                    "priority": t.priority,
                }
                for t in triggers
            ],
            "count": len(triggers),
        }
    except Exception as e:
        logger.error(f"List triggers failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/triggers/{trigger_id}/fire")
async def fire_trigger(
    trigger_id: str,
    context: Dict[str, Any] = Body({}),
):
    """Fire a specific trigger with observability."""
    try:
        from common_lib.modules.triggers.integration_adapter import (
            get_trigger_integration,
        )

        adapter = get_trigger_integration()
        result = await adapter.fire_with_observability(trigger_id, context)

        return {
            "status": "ok",
            "trigger_id": trigger_id,
            "result": result,
        }
    except Exception as e:
        logger.error(f"Fire trigger failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/triggers/stats")
async def trigger_stats(
    api_version: str = Depends(resolve_api_version),
):
    """Get trigger integration statistics."""
    try:
        from common_lib.modules.triggers.integration_adapter import (
            get_trigger_integration,
        )

        return {
            "api_version": api_version,
            "status": "ok",
            "stats": get_trigger_integration().get_stats(),
        }
    except Exception as e:
        logger.error(f"Trigger stats failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Rules
# =============================================================================


@router.get("/rules/stats")
async def rule_stats(
    api_version: str = Depends(resolve_api_version),
):
    """Get rules integration statistics."""
    try:
        from common_lib.modules.rules_engine.integration_adapter import (
            get_rules_integration,
        )

        return {
            "api_version": api_version,
            "status": "ok",
            "stats": get_rules_integration().get_stats(),
        }
    except Exception as e:
        logger.error(f"Rule stats failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Hooks
# =============================================================================


@router.get("/hooks/stats")
async def hook_stats(
    api_version: str = Depends(resolve_api_version),
):
    """Get hook integration statistics."""
    try:
        from common_lib.modules.hooks.integration_adapter import get_hook_integration

        return {
            "api_version": api_version,
            "status": "ok",
            "stats": get_hook_integration().get_stats(),
        }
    except Exception as e:
        logger.error(f"Hook stats failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Notifications
# =============================================================================


@router.get("/notifications/stats")
async def notification_stats(
    api_version: str = Depends(resolve_api_version),
):
    """Get notification analytics."""
    try:
        from common_lib.modules.notification.controller import get_notification_service

        service = get_notification_service()
        return {
            "api_version": api_version,
            "status": "ok",
            "analytics": service.get_analytics(),
            "channels": service.get_channels(),
        }
    except Exception as e:
        logger.error(f"Notification stats failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Observability
# =============================================================================


@router.get("/observability/metrics")
async def observability_metrics(
    api_version: str = Depends(resolve_api_version),
    format: str = Query("json", description="Output format: json or prometheus"),
):
    """Get observability metrics."""
    try:
        from common_lib.modules.observability import get_observability

        obs = get_observability()

        if format == "prometheus":
            from fastapi.responses import PlainTextResponse

            return PlainTextResponse(content=obs.export_prometheus())

        return {
            "api_version": api_version,
            "status": "ok",
            "data": obs.get_all_metrics(),
        }
    except Exception as e:
        logger.error(f"Observability metrics failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/observability/alerts")
async def observability_alerts(
    api_version: str = Depends(resolve_api_version),
):
    """Get active alerts."""
    try:
        from common_lib.modules.observability import get_observability

        obs = get_observability()
        obs.evaluate_alerts()

        return {
            "api_version": api_version,
            "status": "ok",
            "alerts": [
                {
                    "rule_name": a.rule_name,
                    "metric": a.metric,
                    "current_value": a.current_value,
                    "threshold": a.threshold,
                    "severity": a.severity,
                    "triggered_at": a.triggered_at,
                    "message": a.message,
                }
                for a in obs.get_active_alerts()
            ],
            "alert_count": len(obs.get_active_alerts()),
        }
    except Exception as e:
        logger.error(f"Observability alerts failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/observability/reset")
async def observability_reset():
    """Reset all observability metrics."""
    try:
        from common_lib.modules.observability import get_observability

        get_observability().reset()

        return {
            "status": "ok",
            "message": "All observability metrics reset",
        }
    except Exception as e:
        logger.error(f"Observability reset failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Memory Bridge
# =============================================================================


@router.get("/memory/bridge/stats")
async def memory_bridge_stats(
    api_version: str = Depends(resolve_api_version),
):
    """Get memory bridge integration statistics."""
    try:
        from common_lib.modules.integration.memory_bridge import get_memory_bridge

        bridge = get_memory_bridge()
        s = bridge.get_stats()
        return {
            "api_version": api_version,
            "total_events_routed": s.get("events_bridged", 0),
            "events_last_hour": 0,
            "error_rate": s.get("errors", 0) / max(s.get("events_bridged", 1), 1),
            "connected_modules": [
                "core",
                "context",
                "storage",
                "retrieval",
                "semantics",
                "security",
                "federation",
            ],
            "avg_processing_time_ms": 0,
            "uptime_seconds": 0,
            "last_heartbeat": "",
        }
    except Exception as e:
        logger.error(f"Memory bridge stats failed: {e}", exc_info=True)
        return {
            "total_events_routed": 0,
            "events_last_hour": 0,
            "error_rate": 0,
            "connected_modules": [],
            "avg_processing_time_ms": 0,
            "uptime_seconds": 0,
            "last_heartbeat": "",
        }


# =============================================================================
# OpenAPI / Swagger  —  versioned endpoints
# =============================================================================


def _get_openapi_spec(version: str):
    """Generate an OpenAPI spec for a given version."""
    from common_lib.modules.integration.docs.api_docs import (
        generate_openapi_spec as _gen_spec,
    )

    validate_version(version)
    spec = _gen_spec(version=version)
    # Attach version metadata
    spec["x-version"] = spec["info"]["version"]
    spec["x-version-label"] = version
    return spec


@router.get("/openapi.json", include_in_schema=False)
async def integration_openapi_json(
    api_version: str = Depends(resolve_api_version),
):
    """Get the OpenAPI 3.0 specification for RIP tool definitions.

    Supports version negotiation through multiple mechanisms (in priority
    order):
      1. ``Accept-Version`` header  — ``Accept-Version: v2``
      2. ``?version=`` query param   — ``?version=v2``
      3. Default                    — v1

    Version values: ``v1``, ``v2``, ``latest``, or a semver string.
    """
    try:
        return _get_openapi_spec(api_version)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OpenAPI spec generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/openapi.json", include_in_schema=False)
async def integration_openapi_v1_json():
    """Get the OpenAPI 3.0 specification for RIP tool definitions (v1).

    Version-prefixed path — equivalent to ``?version=v1``.
    """
    try:
        return _get_openapi_spec("v1")
    except Exception as e:
        logger.error(f"OpenAPI v1 spec generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v2/openapi.json", include_in_schema=False)
async def integration_openapi_v2_json():
    """Get the OpenAPI 3.0 specification for RIP tool definitions (v2).

    Version-prefixed path — equivalent to ``?version=v2``.
    Currently returns the same tools with version 2.0.0.
    """
    try:
        return _get_openapi_spec("v2")
    except Exception as e:
        logger.error(f"OpenAPI v2 spec generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/bridge/event")
async def fire_memory_bridge_event(payload: Dict[str, Any] = Body(...)):
    """Fire a memory event through the integration bridge."""
    try:
        from common_lib.modules.integration.memory_bridge import (
            get_memory_bridge,
            MemoryEventType,
        )

        bridge = get_memory_bridge()
        event_type = payload.get("event_type", "memory.store")
        data = payload.get("data", {})
        trace_id = payload.get("trace_id")

        result = await bridge.fire_memory_event(
            event_type=MemoryEventType(event_type),
            data=data,
            trace_id=trace_id,
        )
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error(f"Memory bridge event failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
