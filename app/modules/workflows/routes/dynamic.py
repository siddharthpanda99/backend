"""
Dynamic Workflow Execution API — Run any YAML workflow + data-config pair.

Endpoints:
    POST /api/v1/workflows/dynamic/run          — Execute workflow + config
    POST /api/v1/workflows/dynamic/run-stream   — Execute with SSE streaming
    WS   /api/v1/workflows/dynamic/ws/run-stream — Execute with WebSocket streaming
    GET  /api/v1/workflows/dynamic/workflows    — List available workflows
    GET  /api/v1/workflows/dynamic/configs      — List available data-configs
    POST /api/v1/workflows/dynamic/validate     — Validate workflow + config merge (dry run)
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.post("/run")
async def dynamic_run(req: DynamicRunRequest):
    """
    Execute a YAML workflow with a data-config.

    Accepts:
    - workflow: YAML file path, raw YAML string, dict, or workflow_id
    - config: YAML file path, raw YAML string, or dict with data_config block
    - overrides: Runtime parameter overrides

    Returns structured result with status, outputs, timing.
    """
    runner = _get_runner()

    result = await runner.run(
        workflow=req.workflow or req.workflow_id,
        config=req.config,
        workflow_id=req.workflow_id,
        overrides=req.overrides,
        timeout=req.timeout,
    )

    if result.get("status") == "failed" and result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return {"data": result}


@router.post("/run-stream")
async def dynamic_run_stream(req: DynamicRunRequest):
    """
    Execute a YAML workflow with SSE streaming events.
    Same as /run but returns Server-Sent Events for real-time progress.
    """
    runner = _get_runner()

    async def event_generator() -> AsyncGenerator[str, None]:
        async for event in runner.run_stream(
            workflow=req.workflow or req.workflow_id,
            config=req.config,
            workflow_id=req.workflow_id,
            overrides=req.overrides,
        ):
            if isinstance(event, dict) and event.get("event_type") == "keepalive":
                yield ": keepalive\n\n"
            else:
                yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/workflows")
def list_workflows(category: Optional[str] = None):
    """List all available YAML workflows from the registry."""
    runner = _get_runner()
    workflows = runner.list_workflows()
    if category:
        workflows = [w for w in workflows if w.get("category", "").lower() == category.lower()]
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
    WebSocket endpoint for real-time workflow execution streaming.

    Protocol:
      Client → Server:
        { "type": "ping" }                                    — probe / keepalive
        { "type": "run", "workflow": ..., "config": ..., "params": {...} }  — execute
        { "type": "abort" }                                   — cancel running execution

      Server → Client:
        { "type": "pong", "ts": ... }                         — probe response
        { "type": "connected", "server": "..." }              — handshake
        { "type": "progress", "percent": 50, "message": "...", "phase": "..." } — progress
        { "type": "node_start", "node_id": "...", "node_type": "..." }         — node started
        { "type": "node_complete", "node_id": "...", "result": {...} }          — node finished
        { "type": "result", "status": "success", "data": {...} }               — final result
        { "type": "error", "message": "..." }                 — error
    """
    await websocket.accept()
    logger.info("[WS] Client connected to /ws/run-stream")

    # Send handshake
    await websocket.send_json({
        "type": "connected",
        "server": "dynamic-workflow",
        "ts": time.time(),
    })

    running_task = None
    abort_event = None

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
                await websocket.send_json({"type": "pong", "ts": msg.get("ts", time.time())})
                continue

            # ── Abort ──
            if msg_type == "abort":
                if abort_event:
                    abort_event.set()
                    await websocket.send_json({"type": "progress", "percent": 0, "message": "Aborted", "phase": "cancelled"})
                continue

            # ── Run Workflow ──
            if msg_type == "run":
                workflow = msg.get("workflow") or msg.get("workflow_id")
                config = msg.get("config")
                params = msg.get("params") or msg.get("overrides")

                if not workflow:
                    await websocket.send_json({"type": "error", "message": "Missing 'workflow' field"})
                    continue

                # Cancel any previous run
                if abort_event:
                    abort_event.set()

                import asyncio
                abort_event = asyncio.Event()

                # Run in background task
                async def _execute():
                    nonlocal running_task
                    runner = _get_runner()
                    start = time.time()

                    try:
                        async for event in runner.run_stream(
                            workflow=workflow,
                            config=config,
                            overrides=params,
                        ):
                            if abort_event.is_set():
                                await websocket.send_json({"type": "progress", "percent": 0, "message": "Cancelled", "phase": "cancelled"})
                                break

                            if isinstance(event, dict):
                                # Forward progress events
                                if event.get("event_type") == "progress":
                                    await websocket.send_json({
                                        "type": "progress",
                                        "percent": event.get("percent", 0),
                                        "message": event.get("message", ""),
                                        "phase": event.get("phase", ""),
                                    })
                                elif event.get("event_type") == "node_start":
                                    await websocket.send_json({
                                        "type": "node_start",
                                        "node_id": event.get("node_id", ""),
                                        "node_type": event.get("node_type", ""),
                                    })
                                elif event.get("event_type") == "node_complete":
                                    await websocket.send_json({
                                        "type": "node_complete",
                                        "node_id": event.get("node_id", ""),
                                        "result": event.get("result"),
                                    })
                                elif event.get("event_type") == "keepalive":
                                    pass  # skip keepalive over WS
                                else:
                                    # Forward any other event as-is
                                    await websocket.send_json(event)
                            else:
                                # Non-dict event — forward as string
                                await websocket.send_json({"type": "message", "data": str(event)})

                        # Send final result
                        elapsed = time.time() - start
                        await websocket.send_json({
                            "type": "result",
                            "status": "success",
                            "elapsed": round(elapsed, 2),
                        })

                    except Exception as e:
                        logger.error("[WS] Execution error: %s", e)
                        try:
                            await websocket.send_json({"type": "error", "message": str(e)})
                        except Exception:
                            pass
                    finally:
                        running_task = None

                running_task = asyncio.create_task(_execute())
                continue

            # Unknown message type
            await websocket.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info("[WS] Client disconnected")
        if abort_event:
            abort_event.set()
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
        raise HTTPException(status_code=404, detail=f"Workflow not found: {req.workflow or req.workflow_id}")

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
