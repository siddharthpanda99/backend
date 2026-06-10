import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, BackgroundTasks

from common_lib.modules.sync import SyncService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Sync"])


@router.post("/import", response_model=Dict[str, Any])
async def import_entity(
    background_tasks: BackgroundTasks,
    entity_type: str = Query(...),
    file_path: str = Query(...),
    force: bool = False,
):
    return await SyncService.import_entity(entity_type, file_path, force)


@router.post("/export", response_model=Dict[str, Any])
async def export_entity(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    output_path: Optional[str] = None,
    force: bool = False,
):
    return await SyncService.export_entity(entity_type, entity_id, output_path, force)


@router.post("/sync-all", response_model=Dict[str, Any])
async def sync_all_entities(
    background_tasks: BackgroundTasks,
    entity_types: Optional[str] = None,
    direction: str = Query("import"),
    force: bool = False,
):
    return await SyncService.sync_all_entities(entity_types, direction, force)


@router.get("/verify", response_model=Dict[str, Any])
async def verify_consistency(
    entity_types: Optional[str] = None,
):
    return await SyncService.verify_consistency(entity_types)


@router.post("/knowledgebase/sync", response_model=Dict[str, Any])
async def sync_knowledgebase(
    background_tasks: BackgroundTasks,
    force: bool = False,
):
    return await SyncService.sync_knowledgebase(
        schedule_fn=background_tasks.add_task, force=force
    )


@router.post("/knowledgebase/clear", response_model=Dict[str, str])
async def clear_knowledgebase(confirm: bool = Query(False)):
    return await SyncService.clear_knowledgebase(confirm)


@router.get("/knowledgebase/entries", response_model=Dict[str, Any])
async def list_kb_entries(
    skip: int = 0,
    limit: int = 100,
):
    return await SyncService.list_kb_entries(skip, limit)


@router.get("/types", response_model=List[str])
async def list_entity_types():
    return SyncService.list_entity_types()
