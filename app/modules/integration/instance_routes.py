"""Memory Instance Registry API Routes.

Provides REST endpoints for deploying, listing, and tearing down memory instances.
Memory instances are created from Memory Object Builder manifests and attached
to agents, sessions, contexts, workflows, or other objects.

Deploy flow:
  1. Validate manifest structure
  2. Create instance record with status="deploying"
  3. Wire memory_bridge events for enabled segments
  4. Register target binding
  5. Set status="active" and return

Teardown flow:
  1. Unwire all bridge connections
  2. Remove target binding
  3. Archive instance record
  4. Return actions taken
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

router = APIRouter(prefix="/memory/instances", tags=["memory-instances"])

logger = logging.getLogger(__name__)

# =============================================================================
# In-Memory Instance Registry (can be swapped for DB-backed later)
# =============================================================================

_instance_registry: Dict[str, "MemoryInstanceRecord"] = {}

# Track which instances have which bridge connections for clean teardown
_bridge_connections: Dict[str, List[str]] = {}


# =============================================================================
# Data Models
# =============================================================================


class MemoryInstanceRecord(BaseModel):
    id: str
    name: str
    description: str = ""
    manifest: Dict[str, Any] = {}
    target_type: str  # "agent" | "session" | "context" | "workflow" | "object"
    target_id: str
    status: str = "active"  # "active" | "inactive" | "error" | "deploying"
    connected_modules: List[str] = []
    event_count: int = 0
    error_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    last_heartbeat: str = ""


class DeployRequest(BaseModel):
    name: str
    manifest: Dict[str, Any]
    target_type: str = "agent"
    target_id: str
    description: str = ""


class DeployResponse(BaseModel):
    status: str
    instance: MemoryInstanceRecord
    actions_taken: List[str]


class InstanceListResponse(BaseModel):
    status: str
    instances: List[MemoryInstanceRecord]
    count: int


# =============================================================================
# Helper: Extract enabled segments from manifest
# =============================================================================

_VALID_TARGET_TYPES = {"agent", "session", "context", "workflow", "object"}

# Mapping from manifest segment IDs to memory event patterns
_SEGMENT_EVENT_MAP: Dict[str, List[str]] = {
    "core": ["memory.store", "memory.retrieve"],
    "context": ["memory.context.build", "memory.context.compress"],
    "storage": ["memory.store", "memory.batch.store", "memory.cache.clear"],
    "retrieval": ["memory.search", "memory.retrieve"],
    "semantics": ["memory.semantics.clusters", "memory.crystallize"],
    "forecasting": ["memory.forecast"],
    "strategy": ["memory.goal.create", "memory.goal.update"],
    "adaptation": ["memory.adapt"],
    "execution": ["memory.execution.start", "memory.execution.step"],
    "causal": ["memory.causal.discover", "memory.causal.calculus"],
    "testing": ["memory.testing.benchmark", "memory.testing.drift"],
    "driver": ["memory.driver.execute", "memory.driver.block"],
    "security": ["memory.pii.detect", "memory.security.encrypt",
                  "memory.gdpr.forget", "memory.security.decrypt"],
    "observability": ["memory.observability.health", "memory.observability.metrics"],
    "versioning": ["memory.version.restore", "memory.version.diff"],
    "federation": ["memory.federation.sync"],
    "economics": ["memory.economics.cost.track"],
    "marketplace": ["memory.marketplace.item.list"],
    "mql": ["memory.mql.execute", "memory.mql.validate"],
    "multimodal": ["memory.multimodal.image", "memory.multimodal.audio"],
    "persona": ["memory.persona.profile", "memory.persona.interaction"],
    "stores": ["memory.stores.list"],
    "working": ["memory.working.push", "memory.working.promote"],
    "compaction": ["memory.compaction.run", "memory.compaction.automate"],
}


def _extract_enabled_segments(manifest: Dict[str, Any]) -> List[str]:
    """Extract enabled segment IDs from a memory object manifest."""
    segments = manifest.get("segments", {})
    if not segments:
        return []
    # All present segments are considered enabled
    return list(segments.keys())


def _resolve_event_patterns(segment_ids: List[str]) -> List[str]:
    """Resolve segment IDs to their corresponding event patterns."""
    patterns = []
    for seg_id in segment_ids:
        seg_patterns = _SEGMENT_EVENT_MAP.get(seg_id, [])
        patterns.extend(seg_patterns)
    return list(set(patterns))


# =============================================================================
# Helper: Bridge Wiring
# =============================================================================


async def _wire_instance_bridge(
    instance_id: str,
    segment_ids: List[str],
) -> List[str]:
    """Wire memory bridge connections for enabled segments.

    Returns list of actions taken.
    """
    actions = []
    try:
        from common_lib.modules.integration.memory_bridge import get_memory_bridge
        from common_lib.modules.integration.cross_module_bridge import CrossModuleBridge
        from common_lib.modules.integration.event_router import get_event_router

        bridge = get_memory_bridge()
        event_router = get_event_router()
        cm_bridge = CrossModuleBridge()

        event_patterns = _resolve_event_patterns(segment_ids)

        # Wire each event pattern through the bridge
        for pattern in event_patterns:
            try:
                cm_bridge.connect_trigger_to_rules(pattern, "memory_rules")
                actions.append(f"Wired {pattern} → rules")

                # Register a hook binding for this pattern
                from common_lib.modules.integration.event_router import HookBinding
                event_router.bind_hook(
                    HookBinding(
                        event_pattern=pattern,
                        hook_type="post",
                        hook_id=f"instance_{instance_id}",
                    )
                )
                actions.append(f"Bound hook for {pattern}")

                # Track connection for teardown
                if instance_id not in _bridge_connections:
                    _bridge_connections[instance_id] = []
                _bridge_connections[instance_id].append(pattern)

            except Exception as e:
                logger.warning(f"Failed to wire {pattern}: {e}")
                actions.append(f"Failed to wire {pattern}: {e}")

        # Wire cross-module bridge for core memory patterns
        bridge.wire_cross_module_bridge(event_patterns=event_patterns)
        actions.append("Cross-module bridge wired")

        return actions
    except Exception as e:
        logger.error(f"Bridge wiring failed for instance {instance_id}: {e}")
        actions.append(f"Bridge wiring error: {e}")
        return actions


async def _unwire_instance_bridge(instance_id: str) -> List[str]:
    """Unwire all bridge connections for an instance.

    Returns list of actions taken.
    """
    actions = []
    try:
        from common_lib.modules.integration.event_router import get_event_router
        from common_lib.modules.integration.context_propagation import (
            get_context_propagation,
        )

        event_router = get_event_router()

        patterns = _bridge_connections.pop(instance_id, [])

        for pattern in patterns:
            try:
                # Remove routing rules matching this pattern
                existing = event_router.get_routing_rules()
                for rule in existing:
                    if rule.get("event_pattern") == pattern:
                        event_router.remove_routing_rule(rule.get("name"))
                actions.append(f"Unwired {pattern}")
            except Exception as e:
                logger.warning(f"Failed to unwire {pattern}: {e}")

        # Clean up hook bindings
        try:
            existing_hooks = event_router.get_hooks()
            for hook in existing_hooks:
                if hook.get("hook_id") == f"instance_{instance_id}":
                    event_router.remove_hook(hook.get("id") or hook.get("hook_id"))
            actions.append("Removed instance hook bindings")
        except Exception as e:
            logger.warning(f"Failed to remove hooks: {e}")

        return actions
    except Exception as e:
        logger.error(f"Bridge unwiring failed for instance {instance_id}: {e}")
        actions.append(f"Bridge unwiring error: {e}")
        return actions


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("", response_model=DeployResponse)
async def deploy_instance(request: DeployRequest):
    """Deploy a new memory instance from a manifest.

    Validates the manifest, creates the instance record, wires bridge
    connections, and registers target binding.
    """
    try:
        # Validate target type
        if request.target_type not in _VALID_TARGET_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid target_type '{request.target_type}'. "
                       f"Must be one of: {', '.join(sorted(_VALID_TARGET_TYPES))}",
            )

        # Validate manifest has segments
        segments = request.manifest.get("segments", {})
        if not segments:
            raise HTTPException(
                status_code=400,
                detail="Manifest must contain at least one segment in 'segments' key",
            )

        # Validate identity
        identity = request.manifest.get("identity", {})
        if not identity.get("id") or not identity.get("name"):
            raise HTTPException(
                status_code=400,
                detail="Manifest must contain 'identity' with 'id' and 'name'",
            )

        # Check for existing instance on target
        for existing in _instance_registry.values():
            if (existing.target_type == request.target_type
                    and existing.target_id == request.target_id
                    and existing.status == "active"):
                raise HTTPException(
                    status_code=409,
                    detail=f"Target {request.target_type}:{request.target_id} "
                           f"already has active instance '{existing.name}' ({existing.id}). "
                           f"Teardown the existing instance first or use a different target.",
                )

        # Create instance
        now = datetime.now(timezone.utc).isoformat()
        instance_id = f"inst_{uuid.uuid4().hex[:12]}"
        segment_ids = _extract_enabled_segments(request.manifest)

        instance = MemoryInstanceRecord(
            id=instance_id,
            name=request.name,
            description=request.description,
            manifest=request.manifest,
            target_type=request.target_type,
            target_id=request.target_id,
            status="deploying",
            connected_modules=segment_ids,
            created_at=now,
            updated_at=now,
        )

        # Register (status = deploying)
        _instance_registry[instance_id] = instance

        # Wire bridge connections
        wiring_actions = await _wire_instance_bridge(instance_id, segment_ids)
        actions_taken = [
            f"Registered instance {instance_id}",
            f"Target: {request.target_type}:{request.target_id}",
            f"Enabled {len(segment_ids)} segments: {', '.join(segment_ids)}",
            *wiring_actions,
        ]

        # Mark as active
        instance.status = "active"
        instance.updated_at = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"Deployed memory instance '{request.name}' ({instance_id}) "
            f"→ {request.target_type}:{request.target_id} "
            f"with {len(segment_ids)} segments"
        )

        return DeployResponse(
            status="ok",
            instance=instance,
            actions_taken=actions_taken,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deploy instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=InstanceListResponse)
async def list_instances(
    status: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    target_id: Optional[str] = Query(None),
):
    """List all memory instances, optionally filtered."""
    try:
        instances = list(_instance_registry.values())

        if status:
            instances = [i for i in instances if i.status == status]
        if target_type:
            instances = [i for i in instances if i.target_type == target_type]
        if target_id:
            instances = [i for i in instances if i.target_id == target_id]

        # Sort by created_at descending
        instances.sort(key=lambda i: i.created_at, reverse=True)

        return InstanceListResponse(
            status="ok",
            instances=instances,
            count=len(instances),
        )
    except Exception as e:
        logger.error(f"Failed to list instances: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}")
async def get_instance(instance_id: str):
    """Get a specific instance with live health and events."""
    try:
        instance = _instance_registry.get(instance_id)
        if not instance:
            raise HTTPException(
                status_code=404, detail=f"Instance not found: {instance_id}"
            )

        # Fetch live health from observability
        health = None
        try:
            from common_lib.modules.observability import get_observability
            obs = get_observability()
            health = {
                "status": "healthy",
                "health_score": obs.get_all_metrics().get("health_score", 1.0),
                "total_memories": obs.get_all_metrics().get("total_memories", 0),
                "cache_hit_rate": obs.get_all_metrics().get("cache_hit_rate", 0),
                "avg_latency_ms": obs.get_all_metrics().get("avg_latency_ms", 0),
            }
        except Exception as e:
            health = {"status": "unavailable", "error": str(e)}

        # Fetch recent events
        recent_events = []
        try:
            from common_lib.modules.integration.event_router import get_event_router
            router = get_event_router()
            history = router.get_event_history(limit=50)
            # Filter events related to this instance's patterns
            instance_patterns = _resolve_event_patterns(instance.connected_modules)
            recent_events = [
                e for e in history
                if any(p in str(e) for p in instance_patterns)
            ][:20]
        except Exception:
            recent_events = []

        # Update heartbeat
        instance.last_heartbeat = datetime.now(timezone.utc).isoformat()

        return {
            "status": "ok",
            "instance": instance,
            "health": health,
            "recent_events": recent_events,
            "bridge_connections": _bridge_connections.get(instance_id, []),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get instance {instance_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{instance_id}")
async def teardown_instance(instance_id: str):
    """Teardown a memory instance — unwire bridge, remove target binding."""
    try:
        instance = _instance_registry.get(instance_id)
        if not instance:
            raise HTTPException(
                status_code=404, detail=f"Instance not found: {instance_id}"
            )

        if instance.status == "inactive":
            raise HTTPException(
                status_code=400,
                detail=f"Instance {instance_id} is already inactive",
            )

        # Unwire bridge connections
        unwiring_actions = await _unwire_instance_bridge(instance_id)

        actions_taken = [
            f"Unwired {len(_bridge_connections.get(instance_id, []))} bridge connections",
            *unwiring_actions,
            f"Detached from {instance.target_type}:{instance.target_id}",
        ]

        # Mark as inactive (archive)
        instance.status = "inactive"
        instance.updated_at = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"Tore down memory instance '{instance.name}' ({instance_id}) "
            f"from {instance.target_type}:{instance.target_id}"
        )

        return {
            "status": "ok",
            "message": f"Instance {instance_id} torn down",
            "actions_taken": actions_taken,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to teardown instance {instance_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/reload")
async def reload_instance(instance_id: str, manifest: Optional[Dict[str, Any]] = Body(None)):
    """Re-deploy an existing instance with an optional updated manifest."""
    try:
        instance = _instance_registry.get(instance_id)
        if not instance:
            raise HTTPException(
                status_code=404, detail=f"Instance not found: {instance_id}"
            )

        was_active = instance.status == "active"

        # Unwire existing bridge connections
        if was_active:
            await _unwire_instance_bridge(instance_id)
        else:
            _bridge_connections.pop(instance_id, None)

        # Update manifest if provided
        if manifest:
            instance.manifest = manifest
            instance.connected_modules = _extract_enabled_segments(manifest)

        # Rewire
        segment_ids = instance.connected_modules
        wiring_actions = await _wire_instance_bridge(instance_id, segment_ids)

        instance.status = "active"
        instance.updated_at = datetime.now(timezone.utc).isoformat()

        actions_taken = [
            f"Reloaded instance {instance_id}",
            f"Re-wired {len(segment_ids)} segments",
            *wiring_actions,
        ]

        return {
            "status": "ok",
            "instance": instance,
            "actions_taken": actions_taken,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reload instance {instance_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}/events")
async def get_instance_events(
    instance_id: str,
    limit: int = Query(50, ge=1, le=200),
):
    """Get recent events for a specific instance."""
    try:
        instance = _instance_registry.get(instance_id)
        if not instance:
            raise HTTPException(
                status_code=404, detail=f"Instance not found: {instance_id}"
            )

        try:
            from common_lib.modules.integration.event_router import get_event_router
            router = get_event_router()
            history = router.get_event_history(limit=limit)
            instance_patterns = _resolve_event_patterns(instance.connected_modules)
            filtered = [
                e for e in history
                if any(p in str(e) for p in instance_patterns)
            ][:limit]
        except Exception:
            filtered = []

        return {
            "status": "ok",
            "events": filtered,
            "count": len(filtered),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get events for {instance_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}/health")
async def get_instance_health(instance_id: str):
    """Get live health metrics for a specific instance."""
    try:
        instance = _instance_registry.get(instance_id)
        if not instance:
            raise HTTPException(
                status_code=404, detail=f"Instance not found: {instance_id}"
            )

        health = {
            "status": "unknown",
            "instance_id": instance_id,
            "instance_name": instance.name,
            "target": f"{instance.target_type}:{instance.target_id}",
            "connected_modules": instance.connected_modules,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            from common_lib.modules.observability import get_observability
            obs = get_observability()
            metrics = obs.get_all_metrics()
            health.update({
                "status": "healthy",
                "health_score": metrics.get("health_score", 1.0),
                "total_memories": metrics.get("total_memories", 0),
                "active_sessions": metrics.get("active_sessions", 0),
                "cache_hit_rate": metrics.get("cache_hit_rate", 0),
                "avg_latency_ms": metrics.get("avg_latency_ms", 0),
            })
        except Exception as e:
            health["status"] = "unavailable"
            health["error"] = str(e)

        return {"status": "ok", "health": health}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get health for {instance_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary/stats")
async def instance_summary_stats():
    """Get summary statistics across all instances."""
    try:
        instances = list(_instance_registry.values())
        active = [i for i in instances if i.status == "active"]
        inactive = [i for i in instances if i.status == "inactive"]
        error = [i for i in instances if i.status == "error"]

        # Count by target type
        by_target: Dict[str, int] = {}
        for i in instances:
            by_target[i.target_type] = by_target.get(i.target_type, 0) + 1

        return {
            "status": "ok",
            "stats": {
                "total": len(instances),
                "active": len(active),
                "inactive": len(inactive),
                "error": len(error),
                "by_target_type": by_target,
                "total_events_routed": sum(i.event_count for i in instances),
                "total_errors": sum(i.error_count for i in instances),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get instance stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
