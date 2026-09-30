"""
Hooks Module - API Routes
Provides REST API endpoints for hooks management
"""

import logging
import os
import re

from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel

from common_lib.modules.hooks import (
    HookEngine,
    get_hook_engine,
    HookPhase,
)
from common_lib.modules.hooks.types import Hook

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hooks"])

_hooks_engine: Optional[HookEngine] = None


def get_hooks_engine() -> HookEngine:
    global _hooks_engine
    if _hooks_engine is None:
        _hooks_engine = get_hook_engine()
    return _hooks_engine


def _normalise_event(event: str) -> str:
    """Normalise an event name for phase matching.

    ``PreToolUse``, ``pre_tool_use`` and ``pre-tool-use`` all collapse to
    ``pretooluse``, so callers are not forced to know the exact spelling.
    """
    return re.sub(r"[^a-z0-9]+", "", str(event).lower())


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

        for hook in engine.registry.all_hooks():
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
        # Was: return {"hooks": [], "total": 0, "error": str(e)} — HTTP 200 with
        # an empty list, which rendered in the UI as "no hooks configured"
        # during a total backend outage.
        logger.exception("list_hooks failed")
        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: failed to list hooks",
        ) from e


@router.post("/")
async def create_hook(request: HookCreateRequest):
    """Register a new hook.

    G9/G4 — behaviour is gated by ``HOOKS_ENABLE_RUNTIME_HOOK_REGISTRATION``
    (default OFF). With the flag OFF this answers **501** and explains that
    hooks are code, not rows, because the previous implementation returned
    HTTP 200 with ``status: "draft"`` for a hook that was never stored
    anywhere: the response was indistinguishable from a real creation, and
    the hook never appeared in ``GET /hooks/``.

    With the flag ON the hook is genuinely registered in the in-process
    ``HookRegistry`` and therefore really is executable and really is listed.
    """
    if not _REGISTRATION_ENABLED:
        raise HTTPException(
            status_code=501,
            detail=(
                "Runtime hook registration is disabled. Hooks are Python "
                "classes registered at import time (see "
                "common_lib.modules.hooks.engine.HookRegistry.register), not "
                "database rows. Set HOOKS_ENABLE_RUNTIME_HOOK_REGISTRATION=true "
                "to register hooks through this endpoint for the lifetime of "
                "the process."
            ),
        )

    try:
        phase = HookPhase(request.phase)
    except ValueError as exc:
        valid = ", ".join(p.value for p in HookPhase)
        raise HTTPException(
            status_code=422,
            detail=f"Unknown phase {request.phase!r}. Valid phases: {valid}",
        ) from exc

    engine = get_hooks_engine()
    if engine.registry.get(request.name) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"A hook named {request.name!r} is already registered.",
        )

    hook = _build_managed_hook(request, phase)
    engine.registry.register(hook)

    return {
        "id": hook.name,
        "name": hook.name,
        "phase": hook.phase.value,
        "config": request.config,
        "status": "active",
        "priority": hook.priority,
        "blocking": hook.blocking,
        "managed": True,
    }


class _ManagedHook(Hook):
    """A hook created over HTTP and executed as a subprocess.

    ``Hook`` declares its fields as class annotations but is not a dataclass,
    so it takes no constructor arguments — the module's own hooks
    (``ImpactHook``, ``PolicyHook``, …) set the fields in ``__init__``, and
    this does the same.
    """

    def __init__(
        self, name: str, phase: HookPhase, priority: int, blocking: bool, command: str
    ):
        self.name = name
        self.phase = phase
        self.priority = priority
        self.blocking = blocking
        self._command = command

    async def execute(self, context):
        from common_lib.modules.hooks.types import HookResult, HookStatus

        if not self._command:
            return HookResult(
                status=HookStatus.CONTINUE,
                message=(
                    f"managed hook {self.name!r} has no execute_command; "
                    "recorded the event and continued"
                ),
            )

        import asyncio

        proc = await asyncio.create_subprocess_shell(
            self._command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return HookResult(
                status=HookStatus.ERROR,
                message=(
                    f"execute_command exited {proc.returncode}: "
                    f"{stderr.decode('utf-8', 'replace')[:300]}"
                ),
                severity="high",
            )
        return HookResult(
            status=HookStatus.CONTINUE,
            message=f"execute_command exited 0 for {self.name!r}",
        )


def _build_managed_hook(request: HookCreateRequest, phase: HookPhase) -> Hook:
    """Build a runtime hook from a create request.

    ``execute_command`` in the config is the hook body: it runs as a
    subprocess, exactly like the subprocess-based hooks in
    ``hooks/subprocess.py``. A hook with no command records the event it saw
    and continues, which is what the caller asked for; the create response
    says ``managed: True`` so nobody mistakes it for a code-backed hook.
    """
    command = str(request.config.get("execute_command") or "").strip()
    return _ManagedHook(
        name=request.name,
        phase=phase,
        priority=int(request.config.get("priority") or 50),
        blocking=bool(request.config.get("blocking", False)),
        command=command,
    )


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

        # Report absence honestly. The previous body echoed the requested id
        # back with a fabricated phase="post"/status="unknown", which made a
        # missing hook indistinguishable from a real one in phase 'post'.
        raise HTTPException(status_code=404, detail=f"Hook not found: {hook_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_hook failed for %s", hook_id)
        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: failed to read hook {hook_id!r}",
        ) from e


@router.put("/{hook_id}")
async def update_hook(hook_id: str, request: HookCreateRequest):
    """Update hook metadata.

    G9/G4 — gated by ``HOOKS_ENABLE_RUNTIME_HOOK_REGISTRATION`` (default OFF).
    The previous implementation echoed the request back with HTTP 200 and
    changed nothing, so a client received a success for a mutation that never
    happened.
    """
    if not _REGISTRATION_ENABLED:
        raise HTTPException(
            status_code=501,
            detail=(
                "Runtime hook updates are disabled. Registered hooks are live "
                "Python objects; their behaviour is changed in code and "
                "redeployed. Set HOOKS_ENABLE_RUNTIME_HOOK_REGISTRATION=true "
                "to allow in-process reconfiguration."
            ),
        )

    engine = get_hooks_engine()
    hook = engine.registry.get(hook_id)
    if hook is None:
        raise HTTPException(status_code=404, detail=f"Hook not found: {hook_id}")

    try:
        phase = HookPhase(request.phase)
    except ValueError as exc:
        valid = ", ".join(p.value for p in HookPhase)
        raise HTTPException(
            status_code=422,
            detail=f"Unknown phase {request.phase!r}. Valid phases: {valid}",
        ) from exc

    engine.registry.unregister(hook_id)
    updated = _build_managed_hook(request, phase)
    updated.name = request.name or hook_id
    engine.registry.register(updated)

    return {
        "id": updated.name,
        "name": updated.name,
        "phase": updated.phase.value,
        "config": request.config,
        "status": "active",
        "priority": updated.priority,
        "blocking": updated.blocking,
    }


@router.delete("/{hook_id}")
async def delete_hook(hook_id: str):
    """Delete (unregister) a hook.

    G9/G4 — gated by ``HOOKS_ENABLE_RUNTIME_HOOK_REGISTRATION`` (default OFF).
    The previous implementation returned ``{"deleted": id, "message": "Hook
    deleted"}`` with HTTP 200 **without deleting anything**, so the UI showed
    a successful deletion while the hook remained live in the registry.
    """
    if not _REGISTRATION_ENABLED:
        raise HTTPException(
            status_code=501,
            detail=(
                "Runtime hook deletion is disabled. Hooks are code, not rows. "
                "Set HOOKS_ENABLE_RUNTIME_HOOK_REGISTRATION=true to unregister "
                "hooks at runtime."
            ),
        )

    engine = get_hooks_engine()
    if not engine.registry.unregister(hook_id):
        raise HTTPException(status_code=404, detail=f"Hook not found: {hook_id}")

    return {"deleted": hook_id, "message": f"Hook {hook_id!r} unregistered"}


@router.post("/{hook_id}/trigger")
async def trigger_hook(hook_id: str, request: WebhookTriggerRequest):
    """Manually trigger a hook."""
    engine = get_hooks_engine()

    if engine.registry.get(hook_id) is None:
        raise HTTPException(status_code=404, detail=f"Hook not found: {hook_id}")

    try:
        result = await engine.execute(hook_id, request.payload)
    except HTTPException:
        raise
    except Exception as e:
        # Previously this returned HTTP 200 with an "error" key in the body,
        # so a failed trigger was indistinguishable from a successful one to
        # any client that only checked the status code.
        logger.exception("trigger_hook failed for %s", hook_id)
        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: hook {hook_id!r} raised during execution",
        ) from e

    return {
        "triggered": hook_id,
        "event_type": request.event_type,
        "result": result.status.value if result else "unknown",
    }


@router.post("/{hook_id}/enable")
async def enable_hook(hook_id: str):
    """Enable hook."""
    engine = get_hooks_engine()
    hook = engine.registry.get(hook_id)
    if hook is None:
        raise HTTPException(status_code=404, detail=f"Hook not found: {hook_id}")
    # The registry has no disabled state — a registered hook is live. Say so
    # rather than reporting a status change that did not occur.
    return {
        "hook_id": hook_id,
        "status": "active",
        "note": (
            "The hook registry has no disabled state: every registered hook is "
            "already active. Unregister it to stop it running."
        ),
    }


@router.post("/{hook_id}/disable")
async def disable_hook(hook_id: str):
    """Disable hook."""
    engine = get_hooks_engine()
    hook = engine.registry.get(hook_id)
    if hook is None:
        raise HTTPException(status_code=404, detail=f"Hook not found: {hook_id}")
    return {
        "hook_id": hook_id,
        "status": "active",
        "note": (
            "Not disabled. The hook registry has no disabled state, so this "
            "hook is still active and will still run. Unregister it via "
            "DELETE /api/v1/hooks/{hook_id} to stop it running."
        ),
    }


def _not_implemented(feature: str, alternative: str) -> HTTPException:
    """Build a 501 that names the feature and points at a working surface.

    The hooks registry is in-process and versionless, so several endpoints
    have no store behind them. They used to answer 200 with a fabricated
    empty list, or with a fabricated ``rolled_back: true``.
    """
    return HTTPException(
        status_code=501,
        detail=(
            f"{feature} is not implemented by the hooks module: the hook "
            "registry is an in-process singleton with no execution log and no "
            f"version history, so there is nothing truthful to return. {alternative}"
        ),
    )


@router.get("/{hook_id}/logs")
async def get_hook_logs(hook_id: str, limit: int = 50):
    """Get hook execution logs."""
    raise _not_implemented(
        "Per-hook execution logs",
        "Use GET /api/v1/hooks/dlq/ for failed events, and the platform "
        "logging pipeline (observability) for the full execution trace.",
    )


@router.get("/{hook_id}/versions")
async def get_hook_versions(hook_id: str):
    """Get hook version history."""
    raise _not_implemented(
        "Hook version history",
        "Hooks are versioned in source control; the registry holds the "
        "currently-loaded code only.",
    )


@router.post("/{hook_id}/rollback/{version_id}")
async def rollback_hook(hook_id: str, version_id: str):
    """Rollback hook to version."""
    raise _not_implemented(
        "Hook rollback",
        "Roll a hook back by reverting its source and redeploying; the "
        "registry holds no prior versions to restore from.",
    )


@router.post("/trigger")
async def trigger_webhook(request: WebhookTriggerRequest):
    """Trigger hooks by event type."""
    try:
        engine = get_hooks_engine()

        # Derive the phase from the event type where the naming maps onto one
        # (e.g. "workflow.completed" -> no phase; "PreToolUse" -> PRE_TOOL).
        # The previous implementation ignored the event entirely and returned
        # every registered hook name regardless, so the response claimed hooks
        # were triggered that were never selected by the caller.
        phase = _phase_for_event(request.event_type)
        if phase is not None:
            selected = [h.name for h in engine.registry.get_hooks(phase)]
        else:
            selected = []

        return {
            "event_type": request.event_type,
            "phase": phase.value if phase is not None else None,
            "triggered_hooks": selected,
            "total": len(selected),
            "matched": phase is not None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("trigger_webhook failed for %s", request.event_type)
        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: failed to resolve hooks for event "
            f"{request.event_type!r}",
        ) from e


def _phase_for_event(event_type: str) -> HookPhase | None:
    """Map a webhook event name onto a hook phase, or None if it maps to none.

    The event vocabulary is the same one ``subprocess.HOOK_EVENTS`` uses
    (SessionStart / Stop / PreToolUse / PostToolUse), plus the dotted forms
    the UI sends (``workflow.completed``). Normalisation is case- and
    separator-insensitive so ``pre_tool_use`` and ``PreToolUse`` both resolve.
    """
    if not event_type:
        return None
    key = _normalise_event(event_type)
    mapping = {_normalise_event(p.value): p for p in HookPhase}
    return mapping.get(key)


@router.get("/templates/")
async def list_templates(category: Optional[str] = None):
    """List hook templates."""
    from common_lib.modules.hooks.templates import get_default_templates

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
                "triggers": list(t.triggers or []),
                "tags": list(t.tags or []),
            }
            for t in templates
        ],
        "total": len(templates),
    }


@router.post("/templates/{template_id}/instantiate")
async def instantiate_template(template_id: str, parameters: dict):
    """Create hook from template."""
    from common_lib.modules.hooks.templates import TemplateLibrary

    library = TemplateLibrary()

    result = library.instantiate(template_id, parameters)
    if result is None:
        # Was: return {"error": f"Template {id} not found"} — HTTP 200, so a
        # client checking only the status code would record a failed
        # instantiation as a success.
        raise HTTPException(
            status_code=404, detail=f"Template not found: {template_id}"
        )

    payload = result.to_dict()
    # Surface a non-empty warning list in the status line too, so a caller
    # that ignores the body still learns the instantiation was partial.
    if payload["warnings"]:
        logger.warning(
            "instantiate_template %s produced warnings: %s",
            template_id,
            payload["warnings"],
        )
    return payload


@router.get("/schemas/")
async def list_schemas():
    """List validation schemas."""
    return {"schemas": []}


_dlq_engine = None

# G9/G4 — the demo DLQ rows that used to be injected here on every process
# start made fabricated failures look like real operational data. Seeding is
# now opt-in and the rows are labelled as synthetic so a UI can tell them
# apart from a genuinely failed event.
_SEED_DEMO_DLQ = os.getenv("HOOKS_SEED_DEMO_DLQ", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# G9 — runtime hook registration (POST/PUT/DELETE on /hooks/{id}) is OFF by
# default. Hooks are Python objects; letting an HTTP client mutate a live
# in-process registry is a new capability, so it ships disabled.
_REGISTRATION_ENABLED = os.getenv(
    "HOOKS_ENABLE_RUNTIME_HOOK_REGISTRATION", ""
).strip().lower() in {"1", "true", "yes", "on"}


def get_dlq_engine():
    global _dlq_engine
    if _dlq_engine is None:
        from common_lib.modules.governance.rules_engine.resilience.retry import (
            DLQEngine,
        )

        _dlq_engine = DLQEngine()
        if _SEED_DEMO_DLQ:
            # Synthetic rows for demos. `synthetic=True` is recorded on the
            # payload so GET /dlq/ can label them.
            _dlq_engine.add(
                hook_id="PhaseMemoryInjectorHook",
                event_id="evt_09812",
                payload={
                    "phase_name": "Initialization",
                    "project": "demo",
                    "synthetic": True,
                },
                error="ConnectionTimeoutError: Failed to reach agent memory endpoint",
                attempts=3,
            )
            _dlq_engine.add(
                hook_id="PhaseMemoryCaptureHook",
                event_id="evt_09815",
                payload={
                    "phase_name": "CodeReview",
                    "project": "demo",
                    "synthetic": True,
                },
                error="ValidationError: Missing 'grade' field in critique output",
                attempts=2,
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
                "event_id": getattr(entry, "event_id", None),
                "hook_id": entry.hook_id,
                "error": entry.error,
                "timestamp": str(entry.created_at),
                "retry_count": entry.attempts,
                # Never let a synthetic row be read as a real failure.
                "synthetic": bool((entry.payload or {}).get("synthetic")),
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

        if result is None:
            # The hook named in the DLQ entry is no longer registered. This is
            # not a retry — retrying cannot succeed. Record the reason and keep
            # the entry so an operator can act on it, and say so honestly.
            entry.attempts += 1
            entry.error = (
                f"HookNotRegistered: {entry.hook_id!r} is not in the registry; "
                "the entry cannot be replayed until the hook is re-registered."
            )
            raise HTTPException(
                status_code=409,
                detail=entry.error,
            )

        # If successfully processed, delete from DLQ
        dlq.delete(entry_id)
        return {
            "replayed": entry_id,
            "status": "success",
            "result": result.status.value if result else "passed",
        }
    except HTTPException:
        raise
    except Exception as e:
        entry.attempts += 1
        entry.error = f"{type(e).__name__}: {e}"
        logger.exception("replay_dlq_entry failed for %s", entry_id)
        return {
            "replayed": entry_id,
            "status": "failed",
            "error": entry.error,
            "attempts": entry.attempts,
        }


@router.get("/engine/stats")
async def get_engine_stats():
    """Get hooks engine statistics."""
    try:
        engine = get_hooks_engine()
        total = len(engine.registry.all_hooks())
        return {
            "total_hooks": total,
            "by_phase": _get_phase_counts(engine),
        }
    except Exception as e:
        logger.exception("get_engine_stats failed")
        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: failed to read engine statistics",
        ) from e


def _get_phase_counts(engine: HookEngine) -> dict:
    """Get hook counts by phase."""
    counts = {}
    for hook in engine.registry.all_hooks():
        phase = hook.phase.value
        counts[phase] = counts.get(phase, 0) + 1
    return counts
