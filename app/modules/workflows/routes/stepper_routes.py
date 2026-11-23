"""API routes for Workflow Stepper."""

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from common_lib.modules.workflows.stepper.analyzer import analyze_workflow_for_stepper
from common_lib.modules.workflows.stepper.executor import StepperExecutor
from common_lib.modules.workflows.stepper.schemas import (
    StepperAnalysisResponse,
    StepperExecutionRequest,
    StepperExecutionResponse,
    StepperExecutionStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Workflow Stepper"])


# Dependency
def get_stepper_executor() -> StepperExecutor:
    return StepperExecutor()


# =============================================================================
# Analysis
# =============================================================================


@router.get("/{workflow_id}", response_model=StepperAnalysisResponse)
async def get_stepper_analysis(
    workflow_id: str,
    executor: StepperExecutor = Depends(get_stepper_executor),
):
    """Get stepper tabs for a workflow."""
    from common_lib.modules.workflows.standard.registry.workflow_registry import (
        WorkflowRegistry,
    )

    registry = WorkflowRegistry()
    workflow = registry.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Convert from registry format (list of nodes) to API format (dict keyed by node_id)
    api_workflow = _convert_to_api_format(workflow)

    tabs = analyze_workflow_for_stepper(api_workflow)

    return StepperAnalysisResponse(
        workflow_id=workflow_id,
        tabs=tabs,
        total_steps=len(tabs),
        total_nodes=sum(len(tab["nodes"]) for tab in tabs),
    )


def _convert_to_api_format(workflow: dict) -> dict:
    """Convert registry workflow format to API format expected by analyzer."""
    nodes_list = workflow.get("nodes", [])
    api_format = {}
    for node in nodes_list:
        if isinstance(node, dict) and "id" in node:
            node_id = node["id"]
            # Build inputs dict with connections
            inputs = {}
            for key, value in node.get("inputs", {}).items():
                if (
                    isinstance(value, str)
                    and value.startswith("{{")
                    and value.endswith("}}")
                ):
                    # This is a reference to another node's output
                    # For now, skip - the analyzer will handle direct connections
                    pass
                else:
                    inputs[key] = value
            # Add edges as connections
            # The workflow may have edges separately
            api_format[node_id] = {
                "class_type": node.get("toolId") or node.get("type"),
                "inputs": inputs,
                "_meta": {
                    "title": node.get("title") or node.get("toolId") or node.get("type")
                },
            }

    # Process edges to add connection info to inputs
    edges = workflow.get("edges", [])
    for edge in edges:
        if isinstance(edge, dict):
            from_node = edge.get("from") or edge.get("source")
            to_node = edge.get("to") or edge.get("target")
            from_port = edge.get("fromPort") or edge.get("output")
            to_port = edge.get("toPort") or edge.get("input")

            if to_node in api_format and from_node and to_port:
                if "inputs" not in api_format[to_node]:
                    api_format[to_node]["inputs"] = {}
                api_format[to_node]["inputs"][to_port] = [from_node, from_port or 0]

    return api_format


# =============================================================================
# Execution
# =============================================================================


@router.post("/{workflow_id}/execute", response_model=StepperExecutionResponse)
async def execute_stepper(
    workflow_id: str,
    request: StepperExecutionRequest,
    executor: StepperExecutor = Depends(get_stepper_executor),
):
    """Execute workflow in stepper mode."""
    if request.workflow_id != workflow_id:
        raise HTTPException(status_code=400, detail="workflow_id mismatch")

    from common_lib.modules.workflows.standard.registry.workflow_registry import (
        WorkflowRegistry,
    )

    registry = WorkflowRegistry()
    workflow = registry.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    execution_id = await executor.execute(
        workflow_id=workflow_id,
        initial_values=request.initial_values,
        start_step=request.start_step,
        client_id=request.client_id,
    )

    return StepperExecutionResponse(
        execution_id=execution_id,
        status="running",
        stream_url=f"/api/v1/workflows/stepper/{workflow_id}/execute/stream?execution_id={execution_id}",
        current_step=0,
    )


@router.get("/{workflow_id}/execute/stream")
async def stream_stepper_execution(
    workflow_id: str,
    execution_id: UUID = Query(...),
    executor: StepperExecutor = Depends(get_stepper_executor),
):
    """SSE stream for stepper execution progress."""

    async def event_generator():
        import asyncio
        import json

        last_status = None
        while True:
            exec_data = executor.get_status(execution_id)
            if not exec_data:
                yield f"data: {json.dumps({'error': 'Execution not found'})}\n\n"
                break

            status_data = {
                "execution_id": str(exec_data["id"]),
                "status": exec_data["status"],
                "current_step": exec_data["current_step"],
                "total_steps": exec_data["total_steps"],
                "step_status": exec_data["step_status"],
                "node_status": exec_data["node_status"],
                "outputs": exec_data["outputs"],
                "error": exec_data["error"],
            }

            if status_data != last_status:
                yield f"data: {json.dumps(status_data)}\n\n"
                last_status = status_data

            if exec_data["status"] in ("completed", "failed", "cancelled"):
                yield f"data: {json.dumps(status_data)}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{workflow_id}/execute/cancel")
async def cancel_stepper_execution(
    workflow_id: str,
    execution_id: UUID = Query(...),
    executor: StepperExecutor = Depends(get_stepper_executor),
):
    """Cancel a running stepper execution."""
    if executor.cancel(execution_id):
        return {"status": "cancelled", "execution_id": str(execution_id)}
    raise HTTPException(status_code=404, detail="Execution not found or not running")
