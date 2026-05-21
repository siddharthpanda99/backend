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
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

router = APIRouter(prefix="/integration", tags=["integration"])

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
# Integration Status
# =============================================================================


@router.get("/status")
async def integration_status():
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
    limit: int = Query(100, ge=1, le=1000),
):
    """Get recent event routing history."""
    try:
        from common_lib.modules.integration import get_event_router

        return {
            "status": "ok",
            "events": get_event_router().get_event_history(limit),
            "count": limit,
        }
    except Exception as e:
        logger.error(f"Event history failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/rules")
async def routing_rules():
    """Get all routing rules."""
    try:
        from common_lib.modules.integration import get_event_router

        return {
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
    limit: int = Query(50, ge=1, le=500),
):
    """Get recent traces across all modules."""
    try:
        from common_lib.modules.observability import get_observability

        return {
            "status": "ok",
            "traces": get_observability().get_recent_traces(limit),
            "count": limit,
        }
    except Exception as e:
        logger.error(f"List traces failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """Get a specific trace with all spans."""
    try:
        from common_lib.modules.observability import get_observability

        spans = get_observability().get_trace(trace_id)
        if not spans:
            raise HTTPException(status_code=404, detail=f"Trace not found: {trace_id}")

        return {
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
async def trigger_stats():
    """Get trigger integration statistics."""
    try:
        from common_lib.modules.triggers.integration_adapter import (
            get_trigger_integration,
        )

        return {
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
async def rule_stats():
    """Get rules integration statistics."""
    try:
        from common_lib.modules.rules_engine.integration_adapter import (
            get_rules_integration,
        )

        return {
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
async def hook_stats():
    """Get hook integration statistics."""
    try:
        from common_lib.modules.hooks.integration_adapter import get_hook_integration

        return {
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
async def notification_stats():
    """Get notification analytics."""
    try:
        from common_lib.modules.notification.controller import get_notification_service

        service = get_notification_service()
        return {
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
            "status": "ok",
            "data": obs.get_all_metrics(),
        }
    except Exception as e:
        logger.error(f"Observability metrics failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/observability/alerts")
async def observability_alerts():
    """Get active alerts."""
    try:
        from common_lib.modules.observability import get_observability

        obs = get_observability()
        obs.evaluate_alerts()

        return {
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
