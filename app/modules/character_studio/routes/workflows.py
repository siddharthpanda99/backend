"""Workflow routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from common_lib.modules.common.feature_flags import is_enabled
from app.modules.character_studio.routes.models import (
    WorkflowDescriptor,
    WorkflowListResponse,
)

router = APIRouter()

API = "/api/v1/character-studio"


def _guard() -> None:
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        raise HTTPException(status_code=403, detail="character_studio module disabled")


def _call(fn_name: str, *args: Any, **kwargs: Any) -> Any:
    from common_lib.modules.image_processing.character_studio.operations import (
        list_workflows,
        get_workflow,
    )

    return getattr(
        __import__(
            "common_lib.modules.image_processing.character_studio.operations",
            fromlist=[""],
        ),
        fn_name,
    )(*args, **kwargs)


@router.get("/workflows", response_model=WorkflowListResponse)
async def list_workflows() -> WorkflowListResponse:
    """List all character studio workflows."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        list_workflows,
    )

    return list_workflows()


@router.get("/workflows/{workflow_id}", response_model=WorkflowDescriptor)
async def get_workflow(workflow_id: str) -> WorkflowDescriptor:
    """Get a workflow descriptor by ID."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        get_workflow,
    )

    return get_workflow(workflow_id=workflow_id)
