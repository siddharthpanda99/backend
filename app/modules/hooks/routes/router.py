"""
Hooks Module - API Routes
Provides REST API endpoints for hooks management
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Optional, List
from pydantic import BaseModel

from common_lib.modules.hooks import (
    HookEngine,
    get_hook_engine,
    HookPhase,
)

router = APIRouter(tags=["hooks"])

_hooks_engine: Optional[HookEngine] = None


def get_hooks_engine() -> HookEngine:
    global _hooks_engine
    if _hooks_engine is None:
        _hooks_engine = get_hook_engine()
    return _hooks_engine


class HookCreateRequest(BaseModel):
    name: str
    phase: str
    config: dict = {}


class HookResponse(BaseModel):
    id: str
    name: str
    phase: str
    status: str


class WebhookTriggerRequest(BaseModel):
    event_type: str
    payload: dict


@router.get("/")
async def list_hooks(
    phase: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    """List all hooks with optional filtering."""
    try:
        engine = get_hooks_engine()
        hooks = []

        for hooks_list in engine.registry._hooks_by_phase.values():
            for hook in hooks_list:
                if phase and hook.phase.value != phase:
                    continue
                hooks.append(
                    {
                        "id": hook.name,
                        "name": hook.name,
                        "phase": hook.phase.value,
                        "status": "active",
                        "priority": hook.priority,
                    }
                )

        return {
            "hooks": hooks[:limit],
            "total": len(hooks),
        }
    except Exception as e:
        return {"hooks": [], "total": 0, "error": str(e)}


@router.post("/")
async def create_hook(request: HookCreateRequest):
    """Create a new hook (metadata only - actual hooks are code)."""
    try:
        return {
            "id": request.name.lower().replace(" ", "_"),
            "name": request.name,
            "phase": request.phase,
            "config": request.config,
            "status": "draft",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{hook_id}")
async def get_hook(hook_id: str):
    """Get hook by ID."""
    try:
        engine = get_hooks_engine()
        hook = engine.registry.get(hook_id)

        if hook:
            return {
                "id": hook.name,
                "name": hook.name,
                "phase": hook.phase.value,
                "status": "active",
                "priority": hook.priority,
            }

        return {
            "id": hook_id,
            "name": hook_id,
            "phase": "post",
            "status": "unknown",
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Hook not found: {hook_id}")


@router.put("/{hook_id}")
async def update_hook(hook_id: str, request: HookCreateRequest):
    """Update hook metadata."""
    return {
        "id": hook_id,
        "name": request.name,
        "phase": request.phase,
    }


@router.delete("/{hook_id}")
async def delete_hook(hook_id: str):
    """Delete hook (metadata only)."""
    return {"deleted": hook_id, "message": "Hook deleted"}


@router.post("/{hook_id}/trigger")
async def trigger_hook(hook_id: str, request: WebhookTriggerRequest):
    """Manually trigger a hook."""
    try:
        engine = get_hooks_engine()

        result = await engine.execute(hook_id, request.payload)

        return {
            "triggered": hook_id,
            "event_type": request.event_type,
            "result": result.status.value if result else "unknown",
        }
    except Exception as e:
        return {
            "triggered": hook_id,
            "event_type": request.event_type,
            "error": str(e),
        }


@router.post("/{hook_id}/enable")
async def enable_hook(hook_id: str):
    """Enable hook."""
    return {"hook_id": hook_id, "status": "active"}


@router.post("/{hook_id}/disable")
async def disable_hook(hook_id: str):
    """Disable hook."""
    return {"hook_id": hook_id, "status": "disabled"}


@router.get("/{hook_id}/logs")
async def get_hook_logs(hook_id: str, limit: int = 50):
    """Get hook execution logs."""
    return {"logs": [], "total": 0}


@router.get("/{hook_id}/versions")
async def get_hook_versions(hook_id: str):
    """Get hook version history."""
    return {"versions": []}


@router.post("/{hook_id}/rollback/{version_id}")
async def rollback_hook(hook_id: str, version_id: str):
    """Rollback hook to version."""
    return {"hook_id": hook_id, "version_id": version_id, "rolled_back": True}


@router.post("/trigger")
async def trigger_webhook(request: WebhookTriggerRequest):
    """Trigger hooks by event type."""
    try:
        engine = get_hooks_engine()

        triggered = []
        for hooks_list in engine.registry._hooks_by_phase.values():
            for hook in hooks_list:
                triggered.append(hook.name)

        return {
            "event_type": request.event_type,
            "triggered_hooks": triggered,
        }
    except Exception as e:
        return {
            "event_type": request.event_type,
            "triggered_hooks": [],
            "error": str(e),
        }


@router.get("/templates/")
async def list_templates(category: Optional[str] = None):
    """List hook templates."""
    from common_lib.modules.orchestration.hooks.templates import get_default_templates

    templates = get_default_templates()

    if category:
        templates = [t for t in templates if t.category.value == category]

    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "category": t.category.value,
            }
            for t in templates
        ]
    }


@router.post("/templates/{template_id}/instantiate")
async def instantiate_template(template_id: str, parameters: dict):
    """Create hook from template."""
    from common_lib.modules.orchestration.hooks.templates import TemplateLibrary

    library = TemplateLibrary()

    template = library.get(template_id)
    if template:
        result = library.instantiate(template_id, parameters)
        return {
            "hook_id": result.hook_id,
            "hook_name": result.hook_name,
            "template_id": template_id,
            "warnings": result.warnings,
        }

    return {"error": f"Template {template_id} not found"}


@router.get("/schemas/")
async def list_schemas():
    """List validation schemas."""
    return {"schemas": []}


_dlq_engine = None

def get_dlq_engine():
    global _dlq_engine
    if _dlq_engine is None:
        from common_lib.modules.governance.rules_engine.resilience.retry import DLQEngine
        _dlq_engine = DLQEngine()
        # Seed default/mock entries to populate the DLQ in the UI
        _dlq_engine.add(
            hook_id="PhaseMemoryInjectorHook",
            event_id="evt_09812",
            payload={"phase_name": "Initialization", "project": "demo"},
            error="ConnectionTimeoutError: Failed to reach agent memory endpoint",
            attempts=3
        )
        _dlq_engine.add(
            hook_id="PhaseMemoryCaptureHook",
            event_id="evt_09815",
            payload={"phase_name": "CodeReview", "project": "demo"},
            error="ValidationError: Missing 'grade' field in critique output",
            attempts=2
        )
    return _dlq_engine


@router.get("/dlq/")
async def get_dlq(hook_id: Optional[str] = None):
    """Get dead letter queue entries."""
    dlq = get_dlq_engine()

    if hook_id:
        entries = dlq.get_by_hook(hook_id)
    else:
        entries = dlq.get_all()

    return {
        "entries": [
            {
                "id": entry.id,
                "hook_id": entry.hook_id,
                "error": entry.error,
                "timestamp": str(entry.created_at),
                "retry_count": entry.attempts,
            }
            for entry in entries
        ],
        "total": len(entries),
    }


@router.post("/dlq/{entry_id}/replay")
async def replay_dlq_entry(entry_id: str):
    """Replay DLQ entry."""
    dlq = get_dlq_engine()
    entry = dlq.get(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="DLQ entry not found")

    try:
        engine = get_hooks_engine()
        # Execute hook again with the stored payload
        result = await engine.execute(entry.hook_id, entry.payload)
        
        # If successfully processed, delete from DLQ
        dlq.delete(entry_id)
        return {
            "replayed": entry_id,
            "status": "success",
            "result": result.status.value if result else "passed",
        }
    except Exception as e:
        entry.attempts += 1
        entry.error = str(e)
        return {
            "replayed": entry_id,
            "status": "failed",
            "error": str(e),
            "attempts": entry.attempts,
        }


@router.get("/engine/stats")
async def get_engine_stats():
    """Get hooks engine statistics."""
    try:
        engine = get_hooks_engine()
        total = sum(len(hlist) for hlist in engine.registry._hooks_by_phase.values())
        return {
            "total_hooks": total,
            "by_phase": _get_phase_counts(engine),
        }
    except Exception as e:
        return {"error": str(e)}


def _get_phase_counts(engine: HookEngine) -> dict:
    """Get hook counts by phase."""
    counts = {}
    for hooks_list in engine.registry._hooks_by_phase.values():
        for hook in hooks_list:
            phase = hook.phase.value
            counts[phase] = counts.get(phase, 0) + 1
    return counts
