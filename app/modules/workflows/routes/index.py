from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from typing import List, Dict, Any, Optional
import json
from app.modules.common.types.index import APIResponse
from app.modules.database.service.connection import get_session
from app.modules.workflows.service.index import workflow_service
from app.modules.workflows.schemas.index import (
    WorkflowRead,
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowRunRequest,
)

router = APIRouter()

# In-memory workflow state storage (should be DB-backed in production)
_workflow_states = {}


@router.post("/run", response_model=APIResponse[Dict[str, Any]])
def run_workflow(request: WorkflowRunRequest):
    result = workflow_service.run_graph(request.nodes, request.edges, request.inputs)
    return APIResponse(data=result, message="Workflow execution completed")


@router.post("/run-stream")
async def run_workflow_stream(request: WorkflowRunRequest):
    debug_mode = request.inputs.get("debug_mode", False)

    async def event_generator():
        # Create workflow state
        from common_lib.modules.workflows.state import (
            WorkflowState,
            WorkflowStatus,
            PauseSource,
        )
        from common_lib.modules.workflows.observability.events import EventType

        state = WorkflowState(
            execution_id=f"exec_{id(request.nodes) if request.nodes else 'test'}",
            workflow_id="workflow_definition",
            workflow_name="SD Workflow",
        )
        state.debug_mode = debug_mode
        state.total_steps = len(request.nodes)
        state.inputs = request.inputs
        state.status = WorkflowStatus.RUNNING

        _workflow_states[state.execution_id] = state

        async for event in workflow_service.run_graph_stream(
            request.nodes, request.edges, request.inputs
        ):
            # Add state info to event
            event["workflow_state"] = {
                "execution_id": state.execution_id,
                "current_step": state.current_step,
                "total_steps": state.total_steps,
                "progress_percent": state.progress_percent,
                "status": state.status.value,
                "debug_paused": state.debug_paused,
                "state_vars_keys": list(state.state_vars.keys()),
            }
            yield f"data: {json.dumps(event)}\n\n"

            # Check for debug pause
            if state.debug_paused:
                yield f"data: {json.dumps({'event_type': 'DEBUG_PAUSE', 'message': 'Paused for debug'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{execution_id}/pause")
def pause_workflow(
    execution_id: str, source: str = "user", reason: str = "User requested pause"
):
    """Pause a running workflow."""
    from common_lib.modules.workflows.state import PauseSource, WorkflowStatus

    state = _workflow_states.get(execution_id)
    if not state:
        raise HTTPException(status_code=404, detail="Workflow not found")

    src = PauseSource.USER if source == "user" else PauseSource.SYSTEM
    token = state.pause(src, reason)

    return APIResponse(
        data={"resume_token": token, "execution_id": execution_id},
        message="Workflow paused",
    )


@router.post("/{execution_id}/resume")
def resume_workflow(execution_id: str, action: Optional[str] = None):
    """Resume a paused workflow."""
    state = _workflow_states.get(execution_id)
    if not state:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if not state.can_resume():
        raise HTTPException(
            status_code=400, detail="Cannot resume - token expired or not paused"
        )

    state.resume()

    return APIResponse(
        data={"execution_id": execution_id, "status": state.status.value},
        message="Workflow resumed",
    )


@router.get("/{execution_id}/state")
def get_workflow_state(execution_id: str):
    """Get current workflow state."""
    state = _workflow_states.get(execution_id)
    if not state:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return APIResponse(data=state.to_dict(), message="Workflow state retrieved")


@router.get("/{execution_id}/debug-logs")
def get_debug_logs(execution_id: str):
    """Get debug step logs."""
    state = _workflow_states.get(execution_id)
    if not state:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return APIResponse(
        data={
            "debug_mode": state.debug_mode,
            "debug_logs": state.debug_step_logs,
            "steps": [s.to_dict() for s in state.steps],
        },
        message="Debug logs retrieved",
    )


@router.get("/", response_model=APIResponse[List[WorkflowRead]])
def list_workflows(skip: int = 0, limit: int = 100):
    items = workflow_service.get_all(skip=skip, limit=limit)
    return APIResponse(data=items, message="Retrieved list of workflows")


@router.post("/", response_model=APIResponse[WorkflowRead])
def create_workflow(workflow_in: WorkflowCreate):
    item = workflow_service.create(workflow_in)
    return APIResponse(data=item, message="Workflow created successfully")


@router.get("/{id}", response_model=APIResponse[WorkflowRead])
def get_workflow(id: str):
    item = workflow_service.get_by_id(id)
    if not item:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return APIResponse(data=item, message="Workflow retrieved successfully")


@router.put("/{id}", response_model=APIResponse[WorkflowRead])
def update_workflow(id: str, workflow_in: WorkflowUpdate):
    item = workflow_service.update(id, workflow_in)
    return APIResponse(data=item, message="Workflow updated successfully")


@router.delete("/{id}", response_model=APIResponse[dict])
def delete_workflow(id: str):
    workflow_service.delete(id)
    return APIResponse(data={"success": True}, message="Workflow deleted successfully")
