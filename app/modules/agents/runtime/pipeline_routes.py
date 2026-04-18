"""
Pipeline & Checkpoint API Routes
---------------------------
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
import logging

from app.modules.common.types.index import APIResponse
from app.modules.auth.dependencies.index import get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Pipelines"])


class PipelineExecuteRequest(BaseModel):
    pipeline_id: str
    initial_inputs: dict = {}
    context: Optional[dict] = None


class PipelineExecuteResponse(BaseModel):
    execution_id: str
    pipeline_id: str
    status: str
    outputs: dict = {}


class CheckpointCreateRequest(BaseModel):
    session_id: str
    agent_id: str
    step_number: int
    step_name: str
    state_variables: dict = {}
    context: dict = {}


class CheckpointReplayRequest(BaseModel):
    checkpoint_id: str


_executor = None
_checkpoint_manager = None


def set_pipeline_executor(executor):
    global _executor
    _executor = executor


def set_checkpoint_manager(manager):
    global _checkpoint_manager
    _checkpoint_manager = manager


@router.post("/execute", response_model=APIResponse[PipelineExecuteResponse])
async def execute_pipeline(
    request: PipelineExecuteRequest, current_user=Depends(get_current_active_user)
):
    """Execute a pipeline (skill, workflow, or hybrid)."""
    if not _executor:
        raise HTTPException(status_code=500, detail="Pipeline executor not configured")

    try:
        result = await _executor.execute(
            pipeline_id=request.pipeline_id,
            initial_inputs=request.initial_inputs,
            context=request.context,
        )

        return APIResponse(
            data=PipelineExecuteResponse(
                execution_id=result.execution_id,
                pipeline_id=result.pipeline_id,
                status=result.status,
                outputs=result.outputs,
            ),
            message=f"Pipeline {result.status}",
        )
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions", response_model=APIResponse[List[dict]])
async def list_executions(
    pipeline_id: Optional[str] = None,
    limit: int = 20,
    current_user=Depends(get_current_active_user),
):
    """List pipeline executions."""
    if not _executor:
        raise HTTPException(status_code=500, detail="Pipeline executor not configured")

    executions = _executor.list_executions(pipeline_id)

    return APIResponse(
        data=[
            {
                "execution_id": e.execution_id,
                "pipeline_id": e.pipeline_id,
                "status": e.status,
                "duration_ms": e.duration_ms,
                "executed_at": e.executed_at.isoformat(),
            }
            for e in executions[:limit]
        ],
        message=f"Retrieved {len(executions)} executions",
    )


@router.get("/executions/{execution_id}", response_model=APIResponse[dict])
async def get_execution(
    execution_id: str, current_user=Depends(get_current_active_user)
):
    """Get a specific execution."""
    if not _executor:
        raise HTTPException(status_code=500, detail="Pipeline executor not configured")

    execution = _executor.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return APIResponse(
        data={
            "execution_id": execution.execution_id,
            "pipeline_id": execution.pipeline_id,
            "status": execution.status,
            "outputs": execution.outputs,
            "step_results": execution.step_results,
            "duration_ms": execution.duration_ms,
            "executed_at": execution.executed_at.isoformat(),
        },
        message="Execution retrieved",
    )


@router.post("/checkpoints", response_model=APIResponse[dict])
async def create_checkpoint(
    request: CheckpointCreateRequest, current_user=Depends(get_current_active_user)
):
    """Create a checkpoint."""
    if not _checkpoint_manager:
        raise HTTPException(status_code=500, detail="Checkpoint manager not configured")

    try:
        checkpoint_id = await _checkpoint_manager.create_checkpoint(
            session_id=request.session_id,
            agent_id=request.agent_id,
            step_number=request.step_number,
            step_name=request.step_name,
            state_variables=request.state_variables,
            context=request.context,
            messages=[],
            tool_calls=[],
        )

        return APIResponse(
            data={"checkpoint_id": checkpoint_id},
            message="Checkpoint created",
        )
    except Exception as e:
        logger.error(f"Checkpoint creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checkpoints", response_model=APIResponse[List[dict]])
async def list_checkpoints(
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 20,
    current_user=Depends(get_current_active_user),
):
    """List checkpoints."""
    if not _checkpoint_manager:
        raise HTTPException(status_code=500, detail="Checkpoint manager not configured")

    checkpoints = await _checkpoint_manager.list_checkpoints(
        session_id=session_id,
        agent_id=agent_id,
        limit=limit,
    )

    return APIResponse(
        data=[
            {
                "checkpoint_id": c.checkpoint_id,
                "session_id": c.session_id,
                "agent_id": c.agent_id,
                "step_number": c.step_number,
                "created_at": c.created_at.isoformat(),
            }
            for c in checkpoints
        ],
        message=f"Retrieved {len(checkpoints)} checkpoints",
    )


@router.get("/checkpoints/{checkpoint_id}", response_model=APIResponse[dict])
async def get_checkpoint(
    checkpoint_id: str, current_user=Depends(get_current_active_user)
):
    """Get a checkpoint."""
    if not _checkpoint_manager:
        raise HTTPException(status_code=500, detail="Checkpoint manager not configured")

    snapshot = await _checkpoint_manager.get_checkpoint(checkpoint_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    return APIResponse(
        data={
            "snapshot_id": snapshot.snapshot_id,
            "session_id": snapshot.session_id,
            "agent_id": snapshot.agent_id,
            "step_number": snapshot.step_number,
            "step_name": snapshot.step_name,
            "state_variables": snapshot.state_variables,
            "created_at": snapshot.created_at.isoformat(),
        },
        message="Checkpoint retrieved",
    )


@router.post("/checkpoints/{checkpoint_id}/replay", response_model=APIResponse[dict])
async def replay_from_checkpoint(
    checkpoint_id: str, current_user=Depends(get_current_active_user)
):
    """Replay from a checkpoint."""
    if not _checkpoint_manager:
        raise HTTPException(status_code=500, detail="Checkpoint manager not configured")

    result = await _checkpoint_manager.replay_from_checkpoint(checkpoint_id)

    return APIResponse(
        data={
            "checkpoint_id": result.checkpoint_id,
            "status": result.status,
            "message": result.message,
            "snapshot": result.snapshot.model_dump() if result.snapshot else None,
        },
        message=result.message,
    )


@router.post("/checkpoints/{checkpoint_id}", response_model=APIResponse[dict])
async def delete_checkpoint(
    checkpoint_id: str, current_user=Depends(get_current_active_user)
):
    """Delete a checkpoint."""
    if not _checkpoint_manager:
        raise HTTPException(status_code=500, detail="Checkpoint manager not configured")

    success = await _checkpoint_manager.delete_checkpoint(checkpoint_id)

    return APIResponse(
        data={"deleted": success},
        message="Checkpoint deleted" if success else "Failed to delete",
    )
