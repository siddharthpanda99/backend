from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession

# Point back to common_lib for the logic
from common_lib.modules.memory.service import MemoryService
from common_lib.modules.memory.schema import (
    MemoryCreate,
    MemoryUpdate,
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryStatsResponse,
    SharedRegionCreate,
    SharedRegionResponse,
    MemoryCompactRequest,
    HybridRetrievalRequest,
    ContextualViewCreate,
    ContextualViewResponse,
    MemoryVersionRequest,
)
from common_lib.modules.memory.types import MemoryType
from common_lib.modules.memory.config import DEFAULT_MEMORY_CONFIG
from common_lib.modules.memory.retrieval import HybridRetrievalEngine, ContextualView
from common_lib.modules.memory.triggers import MemoryTriggers, TriggerScheduler
from common_lib.modules.memory.versioning import MemoryVersioning
from common_lib.modules.memory.composite import (
    CompositeMemoryStore,
    MemoryContextStore,
    MemoryLinkStore,
    LegoMemoryBuilder,
)
from common_lib.modules.memory.schema import (
    CompositeMemoryCreate,
    CompositeMemoryUpdate,
    LegoBuildRequest,
    LegoAttachRequest,
)

# Backend specific imports for DB
from app.core.settings import get_settings

router = APIRouter(prefix="", tags=["memory"])


def get_db():
    settings = get_settings()
    DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI.replace(
        "postgresql://", "postgresql+psycopg://"
    )
    engine = create_engine(DATABASE_URL, echo=False)

    with DBSession(engine) as session:
        try:
            yield session
        finally:
            session.close()


def get_memory_service(db: DBSession = Depends(get_db)) -> MemoryService:
    return MemoryService(session=db, config=DEFAULT_MEMORY_CONFIG)


@router.post("/", response_model=MemoryResponse)
def store_memory(
    data: MemoryCreate,
    service: MemoryService = Depends(get_memory_service),
):
    memory_id = service.store_memory(
        memory_type=data.memory_type,
        content=data.content,
        agent_id=data.agent_id,
        session_id=data.session_id,
        turn=data.turn,
        importance=data.importance,
    )
    record = service.retrieve_memory(memory_id)
    if not record:
        raise HTTPException(status_code=500, detail="Failed to store memory")
    return MemoryResponse(**record.model_dump(), id=record.id)


@router.get("/{memory_id}", response_model=MemoryResponse)
def get_memory(
    memory_id: int,
    service: MemoryService = Depends(get_memory_service),
):
    record = service.retrieve_memory(memory_id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemoryResponse(**record.model_dump(), id=record.id)


@router.delete("/{memory_id}")
def delete_memory(
    memory_id: int,
    service: MemoryService = Depends(get_memory_service),
):
    if not service.delete_memory(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted", "memory_id": memory_id}


@router.post("/search", response_model=MemorySearchResponse)
def search_memories(
    data: MemorySearchRequest,
    service: MemoryService = Depends(get_memory_service),
):
    results = service.search(
        query=data.query,
        memory_types=data.memory_types,
        agent_id=data.agent_id,
        limit=data.limit,
    )
    memories = [MemoryResponse(**r.model_dump(), id=r.id) for r in results]
    return MemorySearchResponse(memories=memories, total=len(memories))


@router.get("/session/{session_id}")
def get_session_memories(
    session_id: str,
    service: MemoryService = Depends(get_memory_service),
):
    memories = service.get_by_session(session_id)
    return {
        "session_id": session_id,
        "memories": [MemoryResponse(**m.model_dump(), id=m.id) for m in memories],
    }


@router.get("/agent/{agent_id}")
def get_agent_memories(
    agent_id: str,
    service: MemoryService = Depends(get_memory_service),
):
    memories = service.get_by_agent(agent_id)
    return {
        "agent_id": agent_id,
        "memories": [MemoryResponse(**m.model_dump(), id=m.id) for m in memories],
    }


@router.get("/stats", response_model=MemoryStatsResponse)
def get_stats(
    service: MemoryService = Depends(get_memory_service),
):
    stats = service.get_stats()
    return MemoryStatsResponse(**stats)


@router.post("/compact")
def compact_memories(
    data: MemoryCompactRequest,
    service: MemoryService = Depends(get_memory_service),
):
    deleted = service.compact(ttl_days=data.ttl_days, keep_recent=data.keep_recent)
    return {"deleted": deleted}


@router.get("/insights")
def get_insights(
    agent_id: Optional[str] = None,
    service: MemoryService = Depends(get_memory_service),
):
    insights = service.extract_insights(agent_id)
    return {
        "insights": [MemoryResponse(**i.model_dump(), id=i.id) for i in insights],
    }


def get_retrieval_engine(db: DBSession = Depends(get_db)) -> HybridRetrievalEngine:
    return HybridRetrievalEngine(session=db)


def get_contextual_view(db: DBSession = Depends(get_db)) -> ContextualView:
    return ContextualView(session=db)


def get_versioning(db: DBSession = Depends(get_db)) -> MemoryVersioning:
    return MemoryVersioning(session=db)


@router.post("/hybrid/search")
def hybrid_search(
    data: HybridRetrievalRequest,
    engine: HybridRetrievalEngine = Depends(get_retrieval_engine),
):
    results = engine.retrieve_hybrid(
        query=data.query,
        agent_id=data.agent_id,
        limit=data.limit,
        semantic_weight=data.semantic_weight,
        recency_weight=data.recency_weight,
        importance_weight=data.importance_weight,
    )
    return {
        "results": [MemoryResponse(**r.model_dump(), id=r.id) for r in results],
        "total": len(results),
    }


@router.post("/context-views")
def create_context_view(
    data: ContextualViewCreate,
    view: ContextualView = Depends(get_contextual_view),
):
    view_id = view.create_view(
        view_id=data.view_id,
        name=data.name,
        filters=data.filters,
        memory_types=data.memory_types,
        agent_id=data.agent_id,
    )
    return {"view_id": view_id, "status": "created"}


@router.get("/context-views/{view_id}")
def get_context_view(
    view_id: str,
    view: ContextualView = Depends(get_contextual_view),
):
    view_data = view.get_view(view_id)
    if not view_data:
        raise HTTPException(status_code=404, detail="View not found")
    return view_data


@router.get("/context-views/{view_id}/memories")
def get_view_memories(
    view_id: str,
    limit: int = 10,
    view: ContextualView = Depends(get_contextual_view),
):
    memories = view.get_memories_for_view(view_id, limit=limit)
    return {
        "view_id": view_id,
        "memories": [MemoryResponse(**m.model_dump(), id=m.id) for m in memories],
    }


@router.delete("/context-views/{view_id}")
def delete_context_view(
    view_id: str,
    view: ContextualView = Depends(get_contextual_view),
):
    if not view.delete_view(view_id):
        raise HTTPException(status_code=404, detail="View not found")
    return {"status": "deleted", "view_id": view_id}


@router.post("/versions")
def create_version(
    data: MemoryVersionRequest,
    versioning: MemoryVersioning = Depends(get_versioning),
):
    version_id = versioning.create_version(
        memory_id=data.memory_id,
        content=data.content,
        reason=data.reason,
    )
    return {"version_id": version_id, "memory_id": data.memory_id}


@router.get("/versions/{memory_id}")
def get_versions(
    memory_id: int,
    versioning: MemoryVersioning = Depends(get_versioning),
):
    versions = versioning.get_versions(memory_id)
    return {"memory_id": memory_id, "versions": versions}


@router.post("/versions/{memory_id}/rollback/{version_id}")
def rollback_version(
    memory_id: int,
    version_id: int,
    versioning: MemoryVersioning = Depends(get_versioning),
):
    if not versioning.rollback(memory_id, version_id):
        raise HTTPException(status_code=404, detail="Version not found")
    return {"status": "rolled_back", "memory_id": memory_id, "version_id": version_id}


@router.post("/triggers/scan")
def scan_triggers(
    hours: int = 24,
    limit: int = 100,
    db: DBSession = Depends(get_db),
):
    scheduler = TriggerScheduler(session=db)
    results = scheduler.scan_and_trigger(hours=hours, limit=limit)
    return {"results": results, "scanned_hours": hours}


def get_composite_store(db: DBSession = Depends(get_db)) -> CompositeMemoryStore:
    return CompositeMemoryStore(session=db)


def get_lego_builder(db: DBSession = Depends(get_db)) -> LegoMemoryBuilder:
    return LegoMemoryBuilder(session=db)


@router.post("/composites")
def create_composite(
    data: CompositeMemoryCreate,
    store: CompositeMemoryStore = Depends(get_composite_store),
):
    composite_id = store.create_composite(
        name=data.name,
        component_ids=data.component_ids,
        description=data.description,
        agent_id=data.agent_id,
        importance=data.importance,
    )
    return {"id": composite_id, "name": data.name, "status": "created"}


@router.get("/composites")
def list_composites(
    agent_id: Optional[str] = None,
    limit: int = 50,
    store: CompositeMemoryStore = Depends(get_composite_store),
):
    composites = store.list_composites(agent_id=agent_id, limit=limit)
    return {
        "composites": [
            {"id": c.id, "name": c.name, "component_ids": c.component_ids}
            for c in composites
        ]
    }


@router.get("/composites/{composite_id}")
def get_composite(
    composite_id: int,
    store: CompositeMemoryStore = Depends(get_composite_store),
):
    composite = store.get_composite(composite_id)
    if not composite:
        raise HTTPException(status_code=404, detail="Composite not found")
    return {
        "id": composite.id,
        "name": composite.name,
        "description": composite.description,
        "component_ids": composite.component_ids,
        "importance": composite.importance,
    }


@router.get("/composites/{composite_id}/content")
def get_composite_content(
    composite_id: int,
    max_length: int = 2000,
    store: CompositeMemoryStore = Depends(get_composite_store),
):
    content = store.get_composite_content(composite_id, max_length)
    return {"composite_id": composite_id, "content": content}


@router.get("/composites/{composite_id}/components")
def get_composite_components(
    composite_id: int,
    store: CompositeMemoryStore = Depends(get_composite_store),
):
    components = store.get_components(composite_id)
    return {
        "composite_id": composite_id,
        "components": [MemoryResponse(**c.model_dump(), id=c.id) for c in components],
    }


@router.put("/composites/{composite_id}")
def update_composite(
    composite_id: int,
    data: CompositeMemoryUpdate,
    store: CompositeMemoryStore = Depends(get_composite_store),
):
    if data.add_components:
        for cid in data.add_components:
            store.add_component(composite_id, cid)
    if data.remove_components:
        for cid in data.remove_components:
            store.remove_component(composite_id, cid)
    return {"status": "updated", "composite_id": composite_id}


@router.delete("/composites/{composite_id}")
def delete_composite(
    composite_id: int,
    store: CompositeMemoryStore = Depends(get_composite_store),
):
    if not store.delete_composite(composite_id):
        raise HTTPException(status_code=404, detail="Composite not found")
    return {"status": "deleted", "composite_id": composite_id}


@router.post("/lego/build")
def lego_build(
    data: LegoBuildRequest,
    builder: LegoMemoryBuilder = Depends(get_lego_builder),
):
    composite_id = builder.build_composite(
        name=data.name,
        memory_ids=data.component_ids,
        description=data.description,
        agent_id=data.agent_id,
    )

    if data.attach_to_type and data.attach_to_id:
        if data.attach_to_type == "loop":
            builder.attach_to_loop(composite_id, data.attach_to_id)
        elif data.attach_to_type == "workflow":
            builder.attach_to_workflow(composite_id, data.attach_to_id)
        elif data.attach_to_type == "agent":
            builder.attach_to_agent(composite_id, data.attach_to_id)

    return {"id": composite_id, "name": data.name, "status": "built"}


@router.post("/lego/attach")
def lego_attach(
    data: LegoAttachRequest,
    builder: LegoMemoryBuilder = Depends(get_lego_builder),
):
    if data.context_type == "loop":
        builder.attach_to_loop(data.memory_id, data.entity_id)
    elif data.context_type == "workflow":
        builder.attach_to_workflow(data.memory_id, data.entity_id)
    elif data.context_type == "agent":
        builder.attach_to_agent(data.memory_id, data.entity_id)
    elif data.context_type == "procedure":
        builder.attach_to_procedure(data.memory_id, data.entity_id)
    elif data.context_type == "skill":
        builder.attach_to_skill(data.memory_id, data.entity_id)

    return {
        "status": "attached",
        "memory_id": data.memory_id,
        "entity_id": data.entity_id,
    }


@router.get("/lego/entity/{entity_type}/{entity_id}")
def lego_get_for_entity(
    entity_type: str,
    entity_id: str,
    builder: LegoMemoryBuilder = Depends(get_lego_builder),
):
    if entity_type == "loop":
        memories = builder.get_for_loop(entity_id)
    elif entity_type == "workflow":
        memories = builder.get_for_workflow(entity_id)
    elif entity_type == "agent":
        memories = builder.get_for_agent(entity_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid entity_type")

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "memories": [MemoryResponse(**m.model_dump(), id=m.id) for m in memories],
    }
