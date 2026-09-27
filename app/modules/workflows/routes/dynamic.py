"""
Dynamic Workflow Execution API — Run any YAML workflow + data-config pair.

Execution model: runs are dispatched as background jobs via the jobs module
(``common_lib.modules.jobs``) so long workflow work never blocks the FastAPI
event loop.

Endpoints:
    POST /api/v1/workflows/dynamic/run          — Submit run, 202 {job_id}
    GET  /api/v1/workflows/dynamic/job/{job_id} — Job status + result
    POST /api/v1/workflows/dynamic/run-stream   — SSE progress backed by job progress
    WS   /api/v1/workflows/dynamic/ws/run-stream — WS progress backed by job progress
    GET  /api/v1/workflows/dynamic/workflows    — List available workflows
    GET  /api/v1/workflows/dynamic/configs      — List available data-configs
    POST /api/v1/workflows/dynamic/validate     — Validate workflow + config merge (dry run)
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from common_lib.modules.jobs.artifacts import job_dir
from common_lib.modules.jobs.models import JobRecord
from common_lib.modules.jobs.service import get_job_service

from app.modules.jobs.actor import capture_job_actor, owned_job_service
from common_lib.modules.workflows.job_executors import (
    DYNAMIC_RUN_KIND,
    ensure_workflow_executors_registered,
)

logger = logging.getLogger(__name__)

router = APIRouter()

TERMINAL_STATUSES = ("completed", "failed", "cancelled")


class DynamicRunRequest(BaseModel):
    """Request body for dynamic workflow execution."""

    workflow: Optional[str] = Field(
        None,
        description="Workflow YAML path, dict content, or workflow_id from registry",
    )
    config: Optional[str] = Field(
        None,
        description="Data-config YAML path or dict content",
    )
    workflow_id: Optional[str] = Field(
        None,
        description="Workflow ID from registry (alternative to workflow field)",
    )
    overrides: Optional[Dict[str, Any]] = Field(
        None,
        description="Runtime parameter overrides (applied last, highest priority)",
    )
    timeout: int = Field(600, description="Max execution time in seconds")


class DynamicValidateRequest(BaseModel):
    """Request body for dry-run validation."""

    workflow: Optional[str] = None
    config: Optional[str] = None
    workflow_id: Optional[str] = None
    overrides: Optional[Dict[str, Any]] = None


def _get_runner():
    from common_lib.modules.workflows.dynamic_runner import get_dynamic_runner

    return get_dynamic_runner()


def _submit_dynamic_run(
    workflow: Any | None,
    config: Any | None,
    workflow_id: Optional[str],
    overrides: Optional[Dict[str, Any]],
    timeout: int,
) -> JobRecord:
    """Register executors (idempotent) and submit a dynamic-run job."""
    ensure_workflow_executors_registered()
    return owned_job_service().submit(
        kind=DYNAMIC_RUN_KIND,
        params={
            "workflow": workflow,
            "config": config,
            "workflow_id": workflow_id,
            "overrides": overrides or {},
            "timeout": timeout,
        },
        timeout=float(timeout),
    )


def _read_job_result(job_id: str) -> Optional[Dict[str, Any]]:
    """Read the persisted result.json artifact for a job, if present."""
    candidate: Path = job_dir(job_id) / "result.json"
    try:
        if candidate.is_file():
            raw: Any = json.loads(candidate.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {"value": raw}
    except Exception as exc:  # noqa: BLE001
        logger.warning("dynamic: could not read result for job %s: %s", job_id, exc)
    return None


def _job_status_payload(record: JobRecord) -> Dict[str, Any]:
    """Serialize a job record plus its result artifact (when completed)."""
    payload: Dict[str, Any] = record.to_dict()
    if record.status == "completed":
        result: Optional[Dict[str, Any]] = _read_job_result(record.id)
        if result is not None:
            payload["result"] = result
    return payload


async def _poll_job_sse(job_id: str, timeout: int) -> AsyncGenerator[str, None]:
    """Yield SSE progress events backed by job progress until terminal."""
    deadline: float = time.time() + float(timeout) + 30.0
    last_progress: float = -1.0
    yield f"data: {json.dumps({'event_type': 'workflow.started', 'job_id': job_id})}\n\n"
    while True:
        record: JobRecord | None = get_job_service().get(job_id)
        if record is None:
            yield f"data: {json.dumps({'event_type': 'workflow.failed', 'job_id': job_id, 'error': 'job not found'})}\n\n"
            return
        if record.progress != last_progress:
            last_progress = record.progress
            yield f"data: {json.dumps({'event_type': 'progress', 'job_id': job_id, 'percent': record.progress, 'status': record.status})}\n\n"
        if record.status in TERMINAL_STATUSES:
            if record.status == "completed":
                result: Optional[Dict[str, Any]] = _read_job_result(job_id)
                yield f"data: {json.dumps({'event_type': 'workflow.completed', 'job_id': job_id, 'result': result or {}}, default=str)}\n\n"
            else:
                yield f"data: {json.dumps({'event_type': 'workflow.failed', 'job_id': job_id, 'error': record.error or record.status})}\n\n"
            return
        if time.time() > deadline:
            yield f"data: {json.dumps({'event_type': 'workflow.failed', 'job_id': job_id, 'error': 'progress poll timed out'})}\n\n"
            return
        await asyncio.sleep(0.5)


# NOTE: capture_job_actor is attached endpoint-level on the HTTP submit routes
# only — this router also declares a websocket route, and FastAPI does not
# inject Request-backed dependencies into WebSocket route deps (it raises at
# request time). The WS handler below therefore submits un-stamped
# (user_id="").
@router.post("/run", status_code=202, dependencies=[Depends(capture_job_actor)])
def dynamic_run(req: DynamicRunRequest):
    """
    Submit a YAML workflow + data-config run as a background job.

    Returns 202 ``{job_id}`` immediately — the run executes on a jobs worker
    thread, never on the event loop. Poll ``GET /job/{job_id}`` for status
    and the result artifact ref.
    """
    record: JobRecord = _submit_dynamic_run(
        workflow=req.workflow or req.workflow_id,
        config=req.config,
        workflow_id=req.workflow_id,
        overrides=req.overrides,
        timeout=req.timeout,
    )
    return {"job_id": record.id, "status": record.status}


@router.get("/job/{job_id}")
def dynamic_job_status(job_id: str):
    """Return job status, progress, result_refs, and the result (when done)."""
    record: JobRecord | None = get_job_service().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {"data": _job_status_payload(record)}


@router.post("/run-stream", dependencies=[Depends(capture_job_actor)])
async def dynamic_run_stream(req: DynamicRunRequest):
    """
    Submit the run as a background job and stream SSE progress events backed
    by job progress, finishing with ``workflow.completed``/``workflow.failed``.
    """
    record: JobRecord = _submit_dynamic_run(
        workflow=req.workflow or req.workflow_id,
        config=req.config,
        workflow_id=req.workflow_id,
        overrides=req.overrides,
        timeout=req.timeout,
    )
    return StreamingResponse(
        _poll_job_sse(record.id, req.timeout), media_type="text/event-stream"
    )


@router.get("/workflows")
def list_workflows(category: Optional[str] = None):
    """List all available YAML workflows from the registry."""
    runner = _get_runner()
    workflows = runner.list_workflows()
    if category:
        workflows = [
            w for w in workflows if w.get("category", "").lower() == category.lower()
        ]
    return {"data": workflows, "total": len(workflows)}


@router.get("/configs")
def list_configs(workflow_id: Optional[str] = None):
    """List all available data-configs, optionally filtered by workflow_id."""
    runner = _get_runner()
    configs = runner.list_configs(workflow_id=workflow_id)
    return {"data": configs, "total": len(configs)}


# ═══════════════════════════════════════════════════════════════════════════
# WebSocket Streaming Endpoint
# ═══════════════════════════════════════════════════════════════════════════


@router.websocket("/ws/run-stream")
async def dynamic_ws_run_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time workflow execution progress.

    Execution runs as a background job (off the event loop); this socket only
    polls job progress and forwards it. Per-node events are not emitted in
    job mode — clients get coarse ``progress`` + terminal ``result``/``error``.

    Protocol:
      Client → Server:
        { "type": "ping" }                                    — probe / keepalive
        { "type": "run", "workflow": ..., "config": ..., "params": {...} }  — execute
        { "type": "abort" }                                   — cancel running execution

      Server → Client:
        { "type": "pong", "ts": ... }                         — probe response
        { "type": "connected", "server": "..." }              — handshake
        { "type": "progress", "percent": 50, "message": "...", "phase": "..." } — progress
        { "type": "result", "status": "success", "data": {...} }               — final result
        { "type": "error", "message": "..." }                 — error
    """
    await websocket.accept()
    logger.info("[WS] Client connected to /ws/run-stream")

    # Send handshake
    await websocket.send_json(
        {
            "type": "connected",
            "server": "dynamic-workflow",
            "ts": time.time(),
        }
    )

    running_task = None
    current_job_id: Optional[str] = None

    async def _forward_job(job_id: str) -> None:
        """Poll a background job and forward progress/result over WS."""
        nonlocal running_task
        start = time.time()
        last_progress: float = -1.0
        try:
            while True:
                record: JobRecord | None = get_job_service().get(job_id)
                if record is None:
                    await websocket.send_json(
                        {"type": "error", "message": f"Job not found: {job_id}"}
                    )
                    return
                if record.progress != last_progress:
                    last_progress = record.progress
                    await websocket.send_json(
                        {
                            "type": "progress",
                            "percent": record.progress,
                            "message": f"Job {record.status}",
                            "phase": record.status,
                            "job_id": job_id,
                        }
                    )
                if record.status in TERMINAL_STATUSES:
                    elapsed = time.time() - start
                    if record.status == "completed":
                        await websocket.send_json(
                            {
                                "type": "result",
                                "status": "success",
                                "job_id": job_id,
                                "data": _read_job_result(job_id) or {},
                                "elapsed": round(elapsed, 2),
                            }
                        )
                    else:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": record.error or record.status,
                                "job_id": job_id,
                            }
                        )
                    return
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("[WS] Job forward error: %s", e)
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            running_task = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "")

            # ── Ping / Probe ──
            if msg_type == "ping":
                await websocket.send_json(
                    {"type": "pong", "ts": msg.get("ts", time.time())}
                )
                continue

            # ── Abort ──
            if msg_type == "abort":
                if current_job_id:
                    get_job_service().cancel(current_job_id)
                    await websocket.send_json(
                        {
                            "type": "progress",
                            "percent": 0,
                            "message": "Aborted",
                            "phase": "cancelled",
                        }
                    )
                if running_task:
                    running_task.cancel()
                continue

            # ── Run Workflow (submit as background job) ──
            if msg_type == "run":
                workflow = msg.get("workflow") or msg.get("workflow_id")
                config = msg.get("config")
                params = msg.get("params") or msg.get("overrides")

                if not workflow:
                    await websocket.send_json(
                        {"type": "error", "message": "Missing 'workflow' field"}
                    )
                    continue

                # Cancel any previous run
                if current_job_id:
                    get_job_service().cancel(current_job_id)
                if running_task:
                    running_task.cancel()

                # WS submits are un-stamped: FastAPI can't resolve the HTTP
                # identity dependency inside a websocket handler.
                record = _submit_dynamic_run(
                    workflow=workflow,
                    config=config,
                    workflow_id=msg.get("workflow_id"),
                    overrides=params if isinstance(params, dict) else None,
                    timeout=int(msg.get("timeout", 600)),
                )
                current_job_id = record.id
                await websocket.send_json(
                    {
                        "type": "progress",
                        "percent": 0,
                        "message": "Job submitted",
                        "phase": "queued",
                        "job_id": record.id,
                    }
                )
                running_task = asyncio.create_task(_forward_job(record.id))
                continue

            # Unknown message type
            await websocket.send_json(
                {"type": "error", "message": f"Unknown type: {msg_type}"}
            )

    except WebSocketDisconnect:
        logger.info("[WS] Client disconnected")
        if current_job_id:
            get_job_service().cancel(current_job_id)
    except Exception as e:
        logger.error("[WS] Error: %s", e)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass


@router.post("/validate")
def dynamic_validate(req: DynamicValidateRequest):
    """
    Dry-run: merge workflow + config and return the resolved graph
    without executing. Useful for debugging parameter resolution.
    """
    runner = _get_runner()

    wf = runner.load_workflow(req.workflow or req.workflow_id, req.workflow_id)
    if not wf:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {req.workflow or req.workflow_id}",
        )

    cfg = runner.load_config(req.config)
    merged = runner.merge(wf, cfg, req.overrides)

    return {
        "data": {
            "workflow_id": merged.get("id"),
            "node_count": len(merged.get("nodes", [])),
            "edge_count": len(merged.get("edges", [])),
            "resolved_params": merged.get("metadata", {}).get("resolved_params", {}),
            "nodes": [
                {
                    "id": n.get("id"),
                    "type": n.get("type"),
                    "properties": n.get("properties") or n.get("inputs", {}),
                }
                for n in merged.get("nodes", [])
            ],
            "edges": merged.get("edges", []),
        }
    }
