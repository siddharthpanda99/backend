"""
Dynamic Workflow Execution API — Run any YAML workflow + data-config pair.

Endpoints:
    POST /api/v1/workflows/dynamic/run          — Execute workflow + config
    POST /api/v1/workflows/dynamic/run-stream   — Execute with SSE streaming
    GET  /api/v1/workflows/dynamic/workflows    — List available workflows
    GET  /api/v1/workflows/dynamic/configs      — List available data-configs
    POST /api/v1/workflows/dynamic/validate     — Validate workflow + config merge (dry run)
"""
import json
import logging
from typing import Any, Dict, List, Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException
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
