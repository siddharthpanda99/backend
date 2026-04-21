import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Sync"])


class SyncReport(BaseModel):
    files_imported: int = 0
    files_exported: int = 0
    entities_created: int = 0
    entities_processed: int = 0
    imported_ids: List[str] = []
    exported_ids: List[str] = []
    errors: List[str] = []


def _get_sync_manager():
    from common_lib.modules.orchestration.infrastructure.sync.manager import (
        EntitySyncManager,
    )
    from common_lib.paths import get_repo_root

    return EntitySyncManager(
        memory_store=_get_memory_store(),
        templates_root=str(get_repo_root() / "templates"),
    )


def _get_memory_store():
    from common_lib.modules.orchestration.context.memory.services import (
        SQLAlchemyMemoryStore,
    )

    return SQLAlchemyMemoryStore()


@router.post("/import", response_model=Dict[str, Any])
async def import_entity(
    background_tasks: BackgroundTasks,
    entity_type: str = Query(...),
    file_path: str = Query(...),
    force: bool = False,
):
    """
    Import a single entity from file to database.
    """
    sync_manager = _get_sync_manager()

    try:
        success, entity_ids = sync_manager.import_from_file(
            entity_type=entity_type,
            file_path=file_path,
            import_source="api",
            force=force,
        )
        return {
            "success": success,
            "entity_type": entity_type,
            "file_path": file_path,
            "entity_ids": entity_ids,
            "count": len(entity_ids),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")


@router.post("/export", response_model=Dict[str, Any])
async def export_entity(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    output_path: Optional[str] = None,
    force: bool = False,
):
    """
    Export a single entity from database to file.
    """
    sync_manager = _get_sync_manager()

    try:
        success = sync_manager.export_to_file(
            entity_type=entity_type,
            entity_id=entity_id,
            output_path=output_path,
            force=force,
        )
        return {
            "success": success,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "output_path": output_path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")


@router.post("/sync-all", response_model=Dict[str, Any])
async def sync_all_entities(
    background_tasks: BackgroundTasks,
    entity_types: Optional[str] = None,
    direction: str = Query("import"),
    force: bool = False,
):
    """
    Sync all entities between filesystem and database.

    - direction=import: FS -> DB (default)
    - direction=export: DB -> FS
    - entity_types: comma-separated list (default: all)
    """
    sync_manager = _get_sync_manager()

    types_list = None
    if entity_types:
        types_list = [t.strip() for t in entity_types.split(",")]

    try:
        if direction == "export":
            report = sync_manager.sync_all_to_files(
                force=force,
                entity_types=types_list,
            )
        else:
            report = sync_manager.sync_all_from_files(
                force=force,
                entity_types=types_list,
            )

        return {
            "status": "completed",
            "direction": direction,
            "files_imported": report.files_imported,
            "files_exported": report.files_exported,
            "entities_created": report.entities_created,
            "entities_processed": report.entities_processed,
            "imported_ids": report.imported_ids[:50],
            "exported_ids": report.exported_ids[:50],
            "error_count": len(report.errors),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")


@router.get("/verify", response_model=Dict[str, Any])
async def verify_consistency(
    entity_types: Optional[str] = None,
):
    """
    Verify consistency between database and filesystem.
    Returns missing files, orphaned files, and checksum mismatches.
    """
    sync_manager = _get_sync_manager()

    types_list = None
    if entity_types:
        types_list = [t.strip() for t in entity_types.split(",")]

    try:
        report = sync_manager.verify_consistency(entity_types=types_list)

        return {
            "total_entities": report.total_entities,
            "entities_without_files": report.entities_without_files[:20],
            "checksum_mismatches": report.checksum_mismatches[:20],
            "recoverable_from_db": report.recoverable_from_db[:20],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verify failed: {e}")


@router.post("/knowledgebase/sync", response_model=Dict[str, Any])
async def sync_knowledgebase(
    background_tasks: BackgroundTasks,
    force: bool = False,
):
    """
    Import all knowledgebase files to database.
    Uses smart sync (checksum-based skip).
    """
    sync_manager = _get_sync_manager()

    def _run_sync():
        try:
            return sync_manager.sync_all_from_files(
                entity_types=["knowledgebase"],
                force=force,
            )
        except Exception as e:
            logger.error(f"KB sync failed: {e}")
            return None

    background_tasks.add_task(_run_sync)

    return {
        "status": "started",
        "message": "Knowledgebase sync started in background",
    }


@router.post("/knowledgebase/clear", response_model=Dict[str, str])
async def clear_knowledgebase(confirm: bool = Query(False)):
    """
    Clear all knowledgebase entries from database.
    Requires confirm=true.
    """
    if not confirm:
        return {
            "status": "skipped",
            "message": "Set confirm=true to clear KB entries",
        }

    memory = _get_memory_store()

    try:
        with memory._get_session() as session:
            from common_lib.modules.orchestration.knowledgebase.models import (
                KnowledgeBaseRecord,
            )

            session.query(KnowledgeBaseRecord).delete()
            session.commit()

        return {
            "status": "cleared",
            "message": "All knowledgebase entries deleted",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clear failed: {e}")


@router.get("/knowledgebase/entries", response_model=Dict[str, Any])
async def list_kb_entries(
    skip: int = 0,
    limit: int = 100,
):
    """List knowledgebase entries."""
    memory = _get_memory_store()

    try:
        entries = memory.list_kb_entries(skip=skip, limit=limit)
        return {
            "entries": entries,
            "count": len(entries),
            "skip": skip,
            "limit": limit,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List failed: {e}")


@router.get("/types", response_model=List[str])
async def list_entity_types():
    """List all supported entity types."""
    from common_lib.modules.orchestration.infrastructure.sync.constants import (
        ENTITY_MAPPING,
    )

    return list(ENTITY_MAPPING.keys())
