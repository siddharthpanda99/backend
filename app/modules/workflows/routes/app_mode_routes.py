"""API routes for Workflow App Mode."""

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from common_lib.modules.workflows.app_mode.schemas import (
    AppModeConfigCreate,
    AppModeConfigRead,
    AppModeConfigUpdate,
    AppModeExecutionRequest,
    AppModeExecutionResponse,
    AppModeExecutionStatus,
    AppModePublicConfig,
    AppModeShareRequest,
    AppModeShareResponse,
)
from common_lib.modules.workflows.app_mode.service import AppModeService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Workflow App Mode"])


# Dependency
def get_app_mode_service() -> AppModeService:
    return AppModeService()


# =============================================================================
# Config CRUD
# =============================================================================


@router.post("", response_model=AppModeConfigRead, status_code=201)
async def create_app_mode_config(
    config: AppModeConfigCreate,
    service: AppModeService = Depends(get_app_mode_service),
    request: Request = None,
):
    """Create a new App Mode configuration."""
    # TODO: Get user ID from auth
    created_by = None  # UUID(request.state.user_id) if request and hasattr(request.state, 'user_id') else None
    return service.create_config(config, created_by)


@router.get("/{config_id}", response_model=AppModeConfigRead)
async def get_app_mode_config(
    config_id: UUID,
    service: AppModeService = Depends(get_app_mode_service),
):
    """Get App Mode configuration by ID."""
    config = service.get_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="App Mode config not found")
    return config


@router.put("/{config_id}", response_model=AppModeConfigRead)
async def update_app_mode_config(
    config_id: UUID,
    update: AppModeConfigUpdate,
    service: AppModeService = Depends(get_app_mode_service),
):
    """Update App Mode configuration."""
    config = service.update_config(config_id, update)
    if not config:
        raise HTTPException(status_code=404, detail="App Mode config not found")
    return config


@router.delete("/{config_id}", status_code=204)
async def delete_app_mode_config(
    config_id: UUID,
    service: AppModeService = Depends(get_app_mode_service),
):
    """Delete App Mode configuration."""
    if not service.delete_config(config_id):
        raise HTTPException(status_code=404, detail="App Mode config not found")


@router.get("", response_model=list[AppModeConfigRead])
async def list_app_mode_configs(
    workflow_id: Optional[str] = Query(None),
    service: AppModeService = Depends(get_app_mode_service),
):
    """List App Mode configurations."""
    return service.list_configs(workflow_id=workflow_id)


# =============================================================================
# Share Links
# =============================================================================


@router.post("/{config_id}/share", response_model=AppModeShareResponse)
async def create_share_link(
    config_id: UUID,
    request: AppModeShareRequest,
    service: AppModeService = Depends(get_app_mode_service),
):
    """Create a public share link for an App Mode config."""
    if request.app_config_id != config_id:
        raise HTTPException(status_code=400, detail="config_id mismatch")

    result = service.create_share_link(request)
    if not result:
        raise HTTPException(status_code=404, detail="App Mode config not found")
    return result


@router.get("/public/{token}", response_model=AppModePublicConfig)
async def get_public_app_config(
    token: str,
    service: AppModeService = Depends(get_app_mode_service),
):
    """Get public App Mode config via share token (no auth required)."""
    config = service.validate_share_token(token)
    if not config:
        raise HTTPException(status_code=404, detail="Invalid or expired share link")
    return config


# =============================================================================
# Execution
# =============================================================================


@router.post("/{config_id}/execute", response_model=AppModeExecutionResponse)
async def execute_app_mode(
    config_id: UUID,
    request: AppModeExecutionRequest,
    service: AppModeService = Depends(get_app_mode_service),
):
    """Execute an App Mode workflow."""
    if request.app_config_id != config_id:
        raise HTTPException(status_code=400, detail="config_id mismatch")

    try:
        return service.execute(request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{config_id}/execute/stream")
async def stream_execution(
    config_id: UUID,
    execution_id: UUID = Query(...),
    service: AppModeService = Depends(get_app_mode_service),
):
    """SSE stream for App Mode execution progress."""

    async def event_generator():
        import asyncio
        import json

        last_status = None
        while True:
            exec_data = service.get_execution_status(execution_id)
            if not exec_data:
                yield f"data: {json.dumps({'error': 'Execution not found'})}\n\n"
                break

            status_data = {
                "execution_id": str(exec_data.execution_id),
                "status": exec_data.status,
                "progress": exec_data.progress,
                "current_node": exec_data.current_node,
                "outputs": exec_data.outputs,
                "error": exec_data.error,
            }

            # Only send if status changed
            if status_data != last_status:
                yield f"data: {json.dumps(status_data)}\n\n"
                last_status = status_data

            if exec_data.status in ("completed", "failed", "cancelled"):
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
