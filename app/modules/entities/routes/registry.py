"""Registry Routes — Thin API layer delegating to common_lib EntityRegistryService."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, AsyncGenerator

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks, Body
from fastapi.responses import StreamingResponse

from app.modules.common.types.index import APIResponse
from app.core.common_lib_integration import common_memory, sync_entity_to_fs
from app.modules.agents.runtime.core import get_engine_manager
from app.modules.agents.runtime.tools.registry import BUILTIN_TOOL_REGISTRY
from app.modules.entities.services.vector_search import get_search_service

from common_lib.modules.entities.registry_service import (
    EntityRegistryService,
    normalize_description,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Shared service instance
# ---------------------------------------------------------------------------
_registry_svc: Optional[EntityRegistryService] = None


def _get_registry_svc() -> EntityRegistryService:
    global _registry_svc
    if _registry_svc is None:
        em = get_engine_manager()
        reg = EntityRegistryService(
            common_memory=common_memory,
            builtin_tool_registry=BUILTIN_TOOL_REGISTRY,
        )
        if em and getattr(em, "registry_svc", None):
            reg.set_registry_svc(em.registry_svc)
            if hasattr(em.registry_svc, "search_provider") and em.registry_svc.search_provider is None:
                search_svc = get_search_service()
                em.registry_svc.search_provider = search_svc.search
        _registry_svc = reg
    return _registry_svc


def _on_sync(entity_type: str, entity_id: str) -> None:
    """Callback to sync entity to filesystem after create/update."""
    sync_entity_to_fs(entity_type, entity_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/search", response_model=APIResponse[List[Dict[str, Any]]])
async def search_registry(
    q: str = Query(..., description="Search query"),
    type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(10, description="Max results"),
):
    try:
        search_svc = get_search_service()
        results = await search_svc.search(query=q, entity_type=type, limit=limit)
        return APIResponse(data=results, message="Search results retrieved")
    except Exception as e:
        logger.error(f"Registry search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/references", response_model=APIResponse[Dict[str, Any]])
async def list_references(
    category: Optional[str] = Query(None, description="Filter by category"),
    q: Optional[str] = Query(None, description="Semantic search query"),
    limit: int = Query(20, description="Max results"),
):
    try:
        svc = _get_registry_svc()
        results = await svc.list_references(
            category=category,
            query=q,
            limit=limit,
            search_fn=None,
        )
        return APIResponse(data=results, message="References retrieved")
    except Exception as e:
        logger.error(f"Failed to get references: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/progress")
async def sync_progress_stream():
    async def progress_generator() -> AsyncGenerator[str, None]:
        search_svc = get_search_service()
        tracker = search_svc.tracker
        last_sent = None
        while True:
            state = {
                "current": tracker.current,
                "total": tracker.total,
                "status": tracker.status,
                "description": tracker.description,
            }
            if state != last_sent:
                yield f"data: {json.dumps(state)}\n\n"
                last_sent = state
            if tracker.status in ["completed", "error"]:
                await asyncio.sleep(2)
                if tracker.status in ["completed", "error"]:
                    tracker.reset()
                    break
            await asyncio.sleep(0.5)

    return StreamingResponse(progress_generator(), media_type="text/event-stream")


@router.get("/{entity_type}/{entity_id}", response_model=APIResponse[Dict[str, Any]])
async def get_entity(entity_type: str, entity_id: str):
    try:
        svc = _get_registry_svc()
        data = svc.get_entity(entity_type, entity_id)
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"{entity_type.capitalize()} '{entity_id}' not found",
            )
        return APIResponse(
            data=data,
            message=f"{entity_type.capitalize()} retrieved successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get {entity_type} {entity_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=APIResponse[Dict[str, Any]])
async def list_entities(
    entity_type: Optional[str] = Query(
        None, description="Filter by entity type: tools, workflows, agents, skills, etc."
    ),
):
    from app.modules.agents.runtime.routes import available_workflows

    try:
        svc = _get_registry_svc()
        results = await svc.list_entities(
            entity_type=entity_type,
            available_workflows_fn=available_workflows,
        )
        return APIResponse(
            data=results,
            message="Unified entity registry retrieved successfully",
        )
    except Exception as e:
        logger.error(f"Failed to fetch unified registry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/definitions", response_model=APIResponse[List[Dict[str, Any]]])
async def get_node_definitions():
    try:
        svc = _get_registry_svc()
        definitions = svc.get_node_definitions()
        return APIResponse(
            data=definitions, message="Node definitions retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Failed to fetch node definitions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/node_definition", response_model=APIResponse[Dict[str, Any]])
async def create_node_definition(definition: Dict[str, Any]):
    try:
        result = common_memory.save_node_definition(
            entity_id=definition.get("id"),
            definition=definition,
            name=definition.get("name", definition.get("id")),
            category=definition.get("category"),
            tags=definition.get("tags"),
            description=definition.get("description"),
            metadata_json=definition.get("metadata") or definition.get("metadata_json") or {},
            ui=definition.get("ui"),
            properties=definition.get("properties"),
        )
        if result:
            return APIResponse(
                data=result,
                message=f"Node definition '{definition.get('id')}' created successfully",
            )
        raise HTTPException(status_code=400, detail="Failed to create node definition")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create node definition: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/port-types")
async def get_port_types():
    svc = _get_registry_svc()
    ports = svc.get_port_types()
    return {"success": True, "data": ports}


@router.post("/port-types/validate")
async def validate_port_type(port_data: dict):
    svc = _get_registry_svc()
    return svc.validate_port_type(port_data)


@router.get("/stats", response_model=APIResponse[Dict[str, Any]])
async def get_registry_stats():
    from app.modules.agents.runtime.routes import available_workflows

    try:
        svc = _get_registry_svc()
        stats = await svc.get_stats(available_workflows_fn=available_workflows)
        return APIResponse(data=stats, message="Registry statistics retrieved")
    except Exception as e:
        logger.error(f"Failed to get registry stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync", response_model=APIResponse[Dict[str, Any]])
async def sync_registry(
    background_tasks: BackgroundTasks,
    force: bool = False,
    force_sync: bool = False,
    force_reindex: bool = False,
):
    try:
        search_svc = get_search_service()
        registry_svc = _get_registry_svc()
        effective_force_sync = force or force_sync
        effective_force_reindex = force or force_reindex

        background_tasks.add_task(
            search_svc.run_full_lifecycle,
            registry_svc=registry_svc.registry_svc,
            force_sync=effective_force_sync,
            force_reindex=effective_force_reindex,
        )
        return APIResponse(
            data={"status": "started"},
            message="Registry synchronization and indexing started in background.",
        )
    except Exception as e:
        logger.error(f"Registry sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=APIResponse[Dict[str, Any]])
async def create_entity(
    entity_type: str = Body(...), definition: Dict[str, Any] = Body(...)
):
    try:
        svc = _get_registry_svc()
        result = svc.create_entity(entity_type, definition, on_sync=_on_sync)
        return APIResponse(
            data=result,
            message=f"{entity_type.title()} created successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create {entity_type}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{entity_type}/{entity_id}", response_model=APIResponse[Dict[str, Any]])
async def update_entity(entity_type: str, entity_id: str, definition: Dict[str, Any] = Body(...)):
    try:
        svc = _get_registry_svc()
        result = svc.update_entity(entity_type, entity_id, definition, on_sync=_on_sync)
        return APIResponse(
            data=result,
            message=f"{entity_type.title()} updated successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update {entity_type} {entity_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{entity_type}/{entity_id}", response_model=APIResponse[bool])
async def delete_entity(entity_type: str, entity_id: str):
    try:
        svc = _get_registry_svc()
        result = svc.delete_entity(entity_type, entity_id)
        return APIResponse(
            data=result,
            message=f"{entity_type.title()} deleted successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete {entity_type} {entity_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Shared Capability Sections
# ---------------------------------------------------------------------------


@router.get("/sections", response_model=APIResponse[list])
async def list_sections(
    section_type: Optional[str] = Query(None, description="Filter by section type"),
):
    try:
        svc = _get_registry_svc()
        sections = svc.list_sections(section_type=section_type)
        return APIResponse(data=sections, message=f"Found {len(sections)} section(s)")
    except Exception as e:
        logger.error(f"Failed to list sections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sections", response_model=APIResponse[Dict[str, Any]])
async def upsert_section(body: Dict[str, Any] = Body(...)):
    try:
        svc = _get_registry_svc()
        result = svc.upsert_section(body)
        return APIResponse(data=result, message="Section saved")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save section: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Live Agent Preview
# ---------------------------------------------------------------------------


@router.get("/agent/{agent_id}/resolved_prompt", response_model=APIResponse[Dict[str, Any]])
async def get_resolved_prompt(agent_id: str):
    try:
        svc = _get_registry_svc()
        result = svc.get_resolved_prompt(agent_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return APIResponse(data=result, message="Resolved prompt retrieved")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get resolved_prompt for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/{agent_id}/resolve", response_model=APIResponse[Dict[str, Any]])
async def resolve_agent_prompt(agent_id: str):
    try:
        svc = _get_registry_svc()
        resolved = svc.resolve_agent_prompt(agent_id)
        if resolved is None:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return APIResponse(
            data={"agent_id": agent_id, "resolved_prompt": resolved},
            message="Prompt resolved and persisted",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve prompt for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/{agent_id}/export")
async def export_agent_markdown(agent_id: str):
    try:
        svc = _get_registry_svc()
        result = svc.export_agent_markdown(agent_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return APIResponse(data=result, message="Agent exported successfully as markdown")
    except Exception as e:
        logger.error(f"Failed to export agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
