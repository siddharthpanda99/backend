"""Task Agent API Routes — thin router delegating to CLI tasks module."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/task-agent", tags=["task-agent"])


# ── Request/Response Models ──────────────────────────────────────


class TaskSubmitRequest(BaseModel):
    agent: str = Field(default="general-purpose", description="Subagent type")
    description: str = Field(..., description="Short task description")
    prompt: str = Field(..., description="Full task prompt")
    background: bool = Field(default=True, description="Run in background")
    depends_on: List[str] = Field(default_factory=list, description="Dependency task IDs")
    priority: int = Field(default=0, description="Scheduling priority")
    session_id: Optional[str] = Field(None, description="Parent session ID")


class TaskControlRequest(BaseModel):
    task_id: str = Field(..., description="Task ID to control")


class PauseResumeRequest(BaseModel):
    task_id: str = Field(..., description="Task ID")


class SetBackgroundRequest(BaseModel):
    task_id: str = Field(..., description="Task ID")
    background: bool = Field(..., description="True = background, False = foreground")


class SetPriorityRequest(BaseModel):
    task_id: str = Field(..., description="Task ID")
    priority: int = Field(..., description="Priority (higher = runs first)")


class DependencyRequest(BaseModel):
    task_id: str = Field(..., description="Task ID")
    depends_on: str = Field(..., description="Task ID to depend on")


class CloneTaskRequest(BaseModel):
    task_id: str = Field(..., description="Task ID to clone")
    new_description: str = Field(default="", description="New description (optional)")
    new_prompt: str = Field(default="", description="New prompt (optional)")


class BulkTaskRequest(BaseModel):
    task_ids: List[str] = Field(..., description="List of task IDs")


class VContextWriteRequest(BaseModel):
    root_session_id: str = Field(..., description="Root session ID")
    key: str = Field(..., description="Key to write")
    value: Any = Field(..., description="JSON-serializable value")
    ttl_seconds: Optional[int] = Field(None, description="Time-to-live in seconds")
    created_by: Optional[str] = Field(None, description="Writer identifier")


class VContextReadRequest(BaseModel):
    root_session_id: str = Field(..., description="Root session ID")
    key: str = Field(..., description="Key to read")


class PartialWorkRequest(BaseModel):
    root_session_id: str = Field(..., description="Root session ID")
    subagent_id: str = Field(..., description="Subagent ID")
    task_description: str = Field(..., description="Task description")
    partial_result: Any = Field(..., description="Partial result data")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


# ── Helper: Import CLI tasks module ─────────────────────────────


def _get_tasks_module():
    from common_lib.modules.cli.tasks import (
        list_tasks,
        inspect_task,
        get_tasks_by_agent,
        cancel_task,
        kill_task,
        pause_task,
        resume_task,
        restart_task,
        retry_task,
        promote_task,
        force_checkpoint,
        set_task_background,
        detach_subagents,
        set_task_priority,
        get_task_dependencies,
        add_task_dependency,
        remove_task_dependency,
        validate_dependencies,
        get_task_budget,
        get_scheduler_stats,
        get_task_transitions,
        get_task_timeline,
        clone_task,
        render_task_graph,
        bulk_cancel_tasks,
        bulk_pause_tasks,
        bulk_resume_tasks,
        tasks_view_enabled,
    )
    return {
        "list_tasks": list_tasks,
        "inspect_task": inspect_task,
        "get_tasks_by_agent": get_tasks_by_agent,
        "cancel_task": cancel_task,
        "kill_task": kill_task,
        "pause_task": pause_task,
        "resume_task": resume_task,
        "restart_task": restart_task,
        "retry_task": retry_task,
        "promote_task": promote_task,
        "force_checkpoint": force_checkpoint,
        "set_task_background": set_task_background,
        "detach_subagents": detach_subagents,
        "set_task_priority": set_task_priority,
        "get_task_dependencies": get_task_dependencies,
        "add_task_dependency": add_task_dependency,
        "remove_task_dependency": remove_task_dependency,
        "validate_dependencies": validate_dependencies,
        "get_task_budget": get_task_budget,
        "get_scheduler_stats": get_scheduler_stats,
        "get_task_transitions": get_task_transitions,
        "get_task_timeline": get_task_timeline,
        "clone_task": clone_task,
        "render_task_graph": render_task_graph,
        "bulk_cancel_tasks": bulk_cancel_tasks,
        "bulk_pause_tasks": bulk_pause_tasks,
        "bulk_resume_tasks": bulk_resume_tasks,
    }


# ── API Endpoints ───────────────────────────────────────────────


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    tasks = _get_tasks_module()
    enabled = tasks["tasks_view_enabled"]()
    return {"status": "ok", "enabled": enabled, "module": "task_agent"}


# ── Task Query ──────────────────────────────────────────────────


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    include_foreground: bool = Query(default=False, description="Include foreground tasks"),
    agent: Optional[str] = Query(None, description="Filter by agent type"),
):
    """List tasks from the scheduler."""
    tasks = _get_tasks_module()
    if agent:
        return tasks["get_tasks_by_agent"](agent)
    return tasks["list_tasks"](status=status, limit=limit, include_foreground=include_foreground)


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Inspect a single task with full detail."""
    tasks = _get_tasks_module()
    return tasks["inspect_task"](task_id)


@router.get("/tasks/{task_id}/dependencies")
async def get_task_dependencies(task_id: str):
    """Get upstream and downstream dependencies for a task."""
    tasks = _get_tasks_module()
    return tasks["get_task_dependencies"](task_id)


@router.get("/tasks/{task_id}/transitions")
async def get_task_transitions(task_id: str):
    """Get full state transition log for a task."""
    tasks = _get_tasks_module()
    return tasks["get_task_transitions"](task_id)


@router.get("/tasks/{task_id}/timeline")
async def get_task_timeline(task_id: str):
    """Get chronological timeline of all events for a task."""
    tasks = _get_tasks_module()
    return tasks["get_task_timeline"](task_id)


@router.get("/tasks/{task_id}/budget")
async def get_task_budget(task_id: str):
    """Get budget status and usage for a task."""
    tasks = _get_tasks_module()
    return tasks["get_task_budget"](task_id)


@router.get("/tasks/graph")
async def get_task_graph(
    root_task_id: Optional[str] = Query(None, description="Root task for subgraph"),
    max_depth: int = Query(default=10, ge=1, le=50, description="Max graph depth"),
):
    """Render ASCII DAG of task dependencies."""
    tasks = _get_tasks_module()
    return tasks["render_task_graph"](root_task_id=root_task_id, max_depth=max_depth)


@router.get("/scheduler/stats")
async def get_scheduler_stats():
    """Get overall scheduler statistics."""
    tasks = _get_tasks_module()
    return tasks["get_scheduler_stats"]()


@router.get("/tasks/by-agent/{agent}")
async def get_tasks_by_agent(agent: str):
    """Get all tasks for a specific agent type."""
    tasks = _get_tasks_module()
    return tasks["get_tasks_by_agent"](agent)


# ── Task Control ────────────────────────────────────────────────


@router.post("/tasks")
async def submit_task(request: TaskSubmitRequest):
    """Submit a new task to the scheduler."""
    from common_lib.modules.integration.ports.orchestration.task_scheduler_port import (
        get_task_scheduler,
        make_task_spec,
    )

    scheduler = get_task_scheduler()
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Task scheduler unavailable")

    spec = make_task_spec(
        description=request.description,
        prompt=request.prompt,
        agent=request.agent,
        parent_session_id=request.session_id or "",
        background=request.background,
        priority=request.priority,
        depends_on=request.depends_on,
    )
    if spec is None:
        raise HTTPException(status_code=500, detail="Failed to create task spec")

    task_id = scheduler.submit(spec)
    return {"status": "ok", "task_id": task_id, "message": f"Task submitted as {task_id}"}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a task (graceful)."""
    tasks = _get_tasks_module()
    return tasks["cancel_task"](task_id)


@router.post("/tasks/{task_id}/kill")
async def kill_task(task_id: str):
    """Force-terminate a task immediately."""
    tasks = _get_tasks_module()
    return tasks["kill_task"](task_id)


@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    """Pause a queued or running task."""
    tasks = _get_tasks_module()
    return tasks["pause_task"](task_id)


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """Resume a paused task."""
    tasks = _get_tasks_module()
    return tasks["resume_task"](task_id)


@router.post("/tasks/{task_id}/restart")
async def restart_task(task_id: str):
    """Restart a task from the beginning."""
    tasks = _get_tasks_module()
    return tasks["restart_task"](task_id)


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    """Retry a failed/cancelled task."""
    tasks = _get_tasks_module()
    return tasks["retry_task"](task_id)


@router.post("/tasks/{task_id}/promote")
async def promote_task(task_id: str):
    """Promote background task to interactive foreground."""
    tasks = _get_tasks_module()
    return tasks["promote_task"](task_id)


@router.post("/tasks/{task_id}/force-checkpoint")
async def force_checkpoint(task_id: str):
    """Force a running task to checkpoint."""
    tasks = _get_tasks_module()
    return tasks["force_checkpoint"](task_id)


@router.post("/tasks/{task_id}/background")
async def set_task_background(task_id: str, request: SetBackgroundRequest):
    """Toggle background/foreground mode."""
    tasks = _get_tasks_module()
    return tasks["set_task_background"](task_id, request.background)


@router.post("/tasks/{task_id}/priority")
async def set_task_priority(task_id: str, request: SetPriorityRequest):
    """Set scheduling priority (higher = runs first)."""
    tasks = _get_tasks_module()
    return tasks["set_task_priority"](task_id, request.priority)


@router.post("/tasks/{task_id}/clone")
async def clone_task(task_id: str, request: CloneTaskRequest):
    """Clone a task with optional overrides."""
    tasks = _get_tasks_module()
    return tasks["clone_task"](task_id, request.new_description, request.new_prompt)


# ── Dependency Management ──────────────────────────────────────


@router.post("/tasks/{task_id}/dependencies")
async def add_task_dependency(task_id: str, request: DependencyRequest):
    """Add a dependency (DAG edge) to a task."""
    tasks = _get_tasks_module()
    return tasks["add_task_dependency"](task_id, request.depends_on)


@router.delete("/tasks/{task_id}/dependencies/{depends_on}")
async def remove_task_dependency(task_id: str, depends_on: str):
    """Remove a dependency from a task."""
    tasks = _get_tasks_module()
    return tasks["remove_task_dependency"](task_id, depends_on)


@router.get("/dependencies/validate")
async def validate_dependencies(task_id: Optional[str] = Query(None)):
    """Validate dependencies for cycles and unreachable tasks."""
    tasks = _get_tasks_module()
    return tasks["validate_dependencies"](task_id or "")


# ── Bulk Operations ────────────────────────────────────────────


@router.post("/tasks/bulk/cancel")
async def bulk_cancel(request: BulkTaskRequest):
    """Cancel multiple tasks at once."""
    tasks = _get_tasks_module()
    return tasks["bulk_cancel_tasks"](request.task_ids)


@router.post("/tasks/bulk/pause")
async def bulk_pause(request: BulkTaskRequest):
    """Pause multiple tasks at once."""
    tasks = _get_tasks_module()
    return tasks["bulk_pause_tasks"](request.task_ids)


@router.post("/tasks/bulk/resume")
async def bulk_resume(request: BulkTaskRequest):
    """Resume multiple tasks at once."""
    tasks = _get_tasks_module()
    return tasks["bulk_resume_tasks"](request.task_ids)


# ── Session/Subagent Management ───────────────────────────────


@router.post("/subagents/detach")
async def detach_subagents(session_id: str = Query(..., description="Root session ID")):
    """Detach all synchronous subagents for a session (OpenCode parity)."""
    tasks = _get_tasks_module()
    return tasks["detach_subagents"](session_id)


# ── Virtual Context (vcontext) ─────────────────────────────────


@router.post("/vcontext/write")
async def vcontext_write(request: VContextWriteRequest):
    """Write a value to the virtual context."""
    from common_lib.modules.cli.context.vcontext import get_vcontext

    vctx = get_vcontext(request.root_session_id)
    vctx.write(request.key, request.value, ttl_seconds=request.ttl_seconds, created_by=request.created_by)
    return {"status": "ok", "key": request.key}


@router.post("/vcontext/read")
async def vcontext_read(request: VContextReadRequest):
    """Read a value from the virtual context."""
    from common_lib.modules.cli.context.vcontext import get_vcontext

    vctx = get_vcontext(request.root_session_id)
    value = vctx.read(request.key)
    return {"status": "ok", "key": request.key, "value": value}


@router.get("/vcontext/{root_session_id}/snapshot")
async def vcontext_snapshot(root_session_id: str):
    """Get full snapshot of virtual context."""
    from common_lib.modules.cli.context.vcontext import get_vcontext

    vctx = get_vcontext(root_session_id)
    return {"status": "ok", "snapshot": vctx.snapshot()}


@router.get("/vcontext/{root_session_id}/keys")
async def vcontext_keys(root_session_id: str):
    """List all keys in virtual context."""
    from common_lib.modules.cli.context.vcontext import get_vcontext

    vctx = get_vcontext(root_session_id)
    return {"status": "ok", "keys": vctx.keys()}


@router.delete("/vcontext/{root_session_id}/keys/{key}")
async def vcontext_delete(root_session_id: str, key: str):
    """Delete a key from virtual context."""
    from common_lib.modules.cli.context.vcontext import get_vcontext

    vctx = get_vcontext(root_session_id)
    deleted = vctx.delete(key)
    return {"status": "ok", "key": key, "deleted": deleted}


@router.post("/vcontext/{root_session_id}/clear")
async def vcontext_clear(root_session_id: str):
    """Clear all keys in virtual context."""
    from common_lib.modules.cli.context.vcontext import get_vcontext

    vctx = get_vcontext(root_session_id)
    vctx.clear()
    return {"status": "ok", "cleared": True}


@router.get("/vcontext/{root_session_id}/stats")
async def vcontext_stats(root_session_id: str):
    """Get statistics about virtual context backends."""
    from common_lib.modules.cli.context.vcontext import get_vcontext

    vctx = get_vcontext(root_session_id)
    return {"status": "ok", "stats": vctx.get_stats()}


# ── Partial Work Recovery ──────────────────────────────────────


@router.post("/vcontext/partial-work/store")
async def store_partial_work(request: PartialWorkRequest):
    """Store partial work from a subagent for recovery."""
    from common_lib.modules.cli.context.vcontext import store_partial_work

    key = store_partial_work(
        request.root_session_id,
        request.subagent_id,
        request.task_description,
        request.partial_result,
        request.metadata,
    )
    return {"status": "ok", "key": key}


@router.get("/vcontext/partial-work/{root_session_id}")
async def get_partial_work(root_session_id: str, subagent_id: Optional[str] = Query(None)):
    """Retrieve all partial work entries."""
    from common_lib.modules.cli.context.vcontext import get_partial_work

    entries = get_partial_work(root_session_id, subagent_id)
    return {"status": "ok", "entries": entries}


@router.post("/vcontext/partial-work/{root_session_id}/complete")
async def mark_partial_work_completed(root_session_id: str, key: str, final_result: Any):
    """Mark partial work as completed."""
    from common_lib.modules.cli.context.vcontext import mark_completed

    success = mark_completed(root_session_id, key, final_result)
    return {"status": "ok", "key": key, "completed": success}


@router.post("/vcontext/partial-work/{root_session_id}/fail")
async def mark_partial_work_failed(root_session_id: str, key: str, error: str):
    """Mark partial work as failed."""
    from common_lib.modules.cli.context.vcontext import mark_failed

    success = mark_failed(root_session_id, key, error)
    return {"status": "ok", "key": key, "failed": success}


# ── SSE Stream for Real-time Updates ───────────────────────────


async def _task_stream_generator(task_id: Optional[str] = None):
    """SSE generator for real-time task updates."""
    from common_lib.modules.notification.controller import get_notification_service, Channels

    service = get_notification_service()
    queue = service.subscribe(Channels.GLOBAL)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                data = event.get("data", {})
                event_type = event.get("event_type", "")
                if "task" in event_type.lower() or data.get("type") in ("task_result", "task_update"):
                    if task_id and data.get("task_id") != task_id:
                        continue
                    yield f"data: {json.dumps(event, default=str)}\n\n"
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        service.unsubscribe(Channels.GLOBAL, queue)


@router.get("/stream")
async def stream_tasks(task_id: Optional[str] = Query(None)):
    """Server-Sent Events stream for real-time task updates."""
    return StreamingResponse(
        _task_stream_generator(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )