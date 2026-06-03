"""Memory Versioning API Routes."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/versioning", tags=["Memory Versioning"])

logger = logging.getLogger(__name__)


@router.get("/{memory_id}/timeline")
async def get_timeline(memory_id: str):
    try:
        from common_lib.modules.memory.versioning.service import get_versioning_service

        svc = get_versioning_service()
        timeline = await svc.get_timeline(memory_id=memory_id)
        if not timeline:
            raise HTTPException(
                status_code=404, detail=f"Timeline not found for memory: {memory_id}"
            )
        return timeline
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{memory_id}/diff")
async def compute_diff(
    memory_id: str,
    from_version: str = Body(...),
    to_version: str = Body(...),
):
    try:
        from common_lib.modules.memory.versioning.diff import get_diff_service

        svc = get_diff_service()
        return await svc.compute_diff(
            memory_id=memory_id,
            from_version=from_version,
            to_version=to_version,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{memory_id}/restore")
async def restore(
    memory_id: str,
    version: str = Body(...),
):
    try:
        from common_lib.modules.memory.versioning.service import get_versioning_service

        svc = get_versioning_service()
        return await svc.restore(memory_id=memory_id, version=version)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/branches")
async def get_branches(agent_id: Optional[str] = Query(None)):
    try:
        from common_lib.modules.memory.versioning.branches import get_branch_service

        svc = get_branch_service()
        return await svc.list_branches(agent_id=agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/branches")
async def create_branch(
    name: str = Body(...),
    base_version: Optional[str] = Body(None),
    agent_id: Optional[str] = Body(None),
):
    try:
        from common_lib.modules.memory.versioning.branches import get_branch_service

        svc = get_branch_service()
        return await svc.create_branch(
            name=name,
            base_version=base_version,
            agent_id=agent_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/branches/{branch_id}/merge")
async def merge_branch(
    branch_id: str,
    target_branch: str = Body(...),
    strategy: str = Body("recursive"),
):
    try:
        from common_lib.modules.memory.versioning.branches import get_branch_service

        svc = get_branch_service()
        return await svc.merge(
            branch_id=branch_id,
            target_branch=target_branch,
            strategy=strategy,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{agent_id}")
async def get_version_history(
    agent_id: str,
    limit: int = Query(50),
    offset: int = Query(0),
):
    try:
        from common_lib.modules.memory.versioning.history import (
            get_version_history_service,
        )

        svc = get_version_history_service()
        return await svc.get_history(
            agent_id=agent_id,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
