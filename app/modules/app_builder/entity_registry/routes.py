"""
Entity Registry - FastAPI Routes

/api/v1/entity-types/ — CRUD for entity type definitions
/api/v1/entity-types/{id}/versions — Version history
/api/v1/entity-types/{id}/instances — Entity instances
/api/v1/entity-types/ingest — Ingest from YAML/JSON
/api/v1/entity-types/{id}/provision — Provision entity type
"""

import logging
from typing import Optional
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path
from sqlalchemy.orm import Session

from common_lib.modules.integration.ports.data_storage.data_storage_port import get_data_storage_session
from common_lib.modules.exceptions import NotFoundError, ConflictError

from common_lib.modules.app_builder.entity_registry.schemas import (
    APIResponse,
    EntityInstanceListResponse,
    EntityTypeCreate,
    EntityTypeListResponse,
    EntityTypeResponse,
    EntityTypeUpdate,
    EntityTypeVersionResponse,
    EntityInstanceListResponse,
    PipelineExecutionCreate,
    PipelineExecutionResponse,
    PipelineStatusResponse,
    IngestRequest,
    IngestResponse,
    ProvisionRequest,
    ProvisionResponse,
)
from common_lib.modules.app_builder.entity_registry.service import EntityRegistryService, get_entity_registry_service

logger = logging.getLogger(__name__)


# Database session dependency using integration port
def get_db_session() -> Session:
    """Get database session via integration port."""
    session_factory = get_data_storage_session()
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Database session not available")
    return session_factory()


router = APIRouter(prefix="/entity-types", tags=["Entity Registry"])
service = EntityRegistryService()


# ─── Entity Type CRUD ──────────────────────────────────────────────


@router.get("/", response_model=EntityTypeListResponse)
async def list_entity_types(
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status (active/deprecated/archived)"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Page size"),
    db: Session = Depends(get_db_session),
):
    """List all entity types with optional filtering."""
    items, total = service.list_entity_types(
        db, category=category, status=status, search=search, page=page, page_size=page_size
    )
    return EntityTypeListResponse(
        items=[EntityTypeResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{entity_type_id}", response_model=EntityTypeResponse)
async def get_entity_type(
    entity_type_id: str,
    db: Session = Depends(get_db_session),
):
    """Get a single entity type by ID."""
    entity_type = service.get_entity_type(db, entity_type_id)
    if not entity_type:
        raise HTTPException(status_code=404, detail=f"Entity type '{entity_type_id}' not found")
    return entity_type


@router.post("/", response_model=EntityTypeResponse, status_code=201)
async def create_entity_type(
    data: EntityTypeCreate,
    db: Session = Depends(get_db_session),
):
    """Create a new entity type definition."""
    try:
        entity_type = service.create_entity_type(db, data.definition)
        return entity_type
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/{entity_type_id}", response_model=EntityTypeResponse)
async def update_entity_type(
    entity_type_id: str,
    data: EntityTypeUpdate,
    db: Session = Depends(get_db_session),
):
    """Update an existing entity type definition."""
    try:
        updates = data.model_dump(exclude_unset=True)
        entity_type = service.update_entity_type(db, entity_type_id, updates)
        if not entity_type:
            raise HTTPException(status_code=404, detail=f"Entity type '{entity_type_id}' not found")
        return entity_type
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{entity_type_id}", response_model=APIResponse)
async def delete_entity_type(
    entity_type_id: str,
    db: Session = Depends(get_db_session),
):
    """Archive an entity type (soft delete)."""
    success = service.delete_entity_type(db, entity_type_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Entity type '{entity_type_id}' not found")
    return APIResponse(success=True, message=f"Entity type '{entity_type_id}' archived")


# ─── Version History ───────────────────────────────────────────────


@router.get("/{entity_type_id}/versions", response_model=list)
async def get_entity_type_versions(
    entity_type_id: str,
    db: Session = Depends(get_db_session),
):
    """Get version history for an entity type."""
    from common_lib.modules.app_builder.entity_registry.schemas import EntityTypeVersionResponse
    versions = service.get_entity_type_versions(db, entity_type_id)
    return [EntityTypeVersionResponse.model_validate(v) for v in versions]


@router.post("/{entity_type_id}/versions/{version_id}/restore", response_model="EntityTypeResponse")
async def restore_entity_type_version(
    entity_type_id: str,
    version_id: str,
    db: Session = Depends(get_db_session),
):
    """Restore an entity type to a previous version."""
    try:
        entity_type = service.restore_entity_type_version(db, entity_type_id, version_id)
        return entity_type
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─── Entity Instances ──────────────────────────────────────────────


@router.get("/{entity_type_id}/instances", response_model=EntityInstanceListResponse)
async def list_entity_instances(
    entity_type_id: str = Path(..., description="Entity type ID"),
    table_name: Optional[str] = Query(None, description="Filter by table name"),
    search: Optional[str] = Query(None, description="Search in instance data"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Page size"),
    db: Session = Depends(get_db_session),
):
    """List entity instances with optional filtering."""
    items, total = service.list_entity_instances(
        db,
        entity_type_id=entity_type_id,
        table_name=table_name,
        search=search,
        page=page,
        page_size=page_size,
    )
    return EntityInstanceListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ─── Pipeline Executions ────────────────────────────────────────────


@router.post("/pipelines", response_model=PipelineExecutionResponse, status_code=201)
async def create_pipeline_execution(
    data: PipelineExecutionCreate,
    db: Session = Depends(get_db_session),
):
    """Create a new pipeline execution record."""
    execution = service.create_pipeline_execution(
        db,
        data.schema_definition,
        entity_type_id=data.entity_type_id,
        target_db_config=data.target_db_config,
    )
    return execution


@router.get("/pipelines/{execution_id}", response_model=PipelineExecutionResponse)
async def get_pipeline_execution(
    execution_id: str,
    db: Session = Depends(get_db_session),
):
    """Get pipeline execution by ID."""
    execution = service.get_pipeline_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail=f"Pipeline execution '{execution_id}' not found")
    return execution


@router.get("/pipelines", response_model=list)
async def list_pipeline_executions(
    entity_type_id: Optional[str] = Query(None, description="Filter by entity type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Page size"),
    db: Session = Depends(get_db_session),
):
    """List pipeline executions with optional filtering."""
    executions = service.list_pipeline_executions(
        db,
        entity_type_id=entity_type_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return executions


@router.patch("/pipelines/{execution_id}", response_model=PipelineExecutionResponse)
async def update_pipeline_execution(
    execution_id: str,
    status: Optional[str] = Body(None, description="Status"),
    current_step: Optional[str] = Body(None, description="Current step"),
    checkpoint: Optional[dict] = Body(None, description="Checkpoint data"),
    error: Optional[str] = Body(None, description="Error message"),
    db: Session = Depends(get_db_session),
):
    """Update pipeline execution status."""
    execution = service.update_pipeline_execution(
        db, execution_id, status=status, current_step=current_step, checkpoint=checkpoint, error=error
    )
    if not execution:
        raise HTTPException(status_code=404, detail=f"Pipeline execution '{execution_id}' not found")
    return execution


@router.get("/pipelines", response_model=list)
async def list_pipelines(
    entity_type_id: Optional[str] = Query(None, description="Filter by entity type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Page size"),
    db: Session = Depends(get_db_session),
):
    """List pipeline executions."""
    executions = service.list_pipeline_executions(
        db,
        entity_type_id=entity_type_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return executions


# ─── Ingest / Provision ────────────────────────────────────────────


@router.post("/ingest", response_model=IngestResponse)
async def ingest_entity_type(
    request: IngestRequest,
    db: Session = Depends(get_db_session),
):
    """Ingest entity type definition from YAML/JSON content."""
    from common_lib.modules.app_builder.entity_registry.service import ingest_entity_type
    result = ingest_entity_type(db, request.content, request.format, request.overwrite)
    return result


@router.post("/{entity_type_id}/provision", response_model=ProvisionResponse)
async def provision_entity_type(
    entity_type_id: str,
    request: ProvisionRequest,
    db: Session = Depends(get_db_session),
):
    """Provision an entity type (run full pipeline)."""
    from common_lib.modules.app_builder.entity_registry.service import provision_entity_type
    result = provision_entity_type(
        db,
        entity_type_id,
        environment=request.environment,
        dry_run=request.dry_run,
        skip_migrations=request.skip_migrations,
        skip_seeding=request.skip_seeding,
        skip_testing=request.skip_testing,
    )
    return result


@router.get("/{entity_type_id}/status", response_model=PipelineStatusResponse)
async def get_provision_status(
    entity_type_id: str,
    db: Session = Depends(get_db_session),
):
    """Get provisioning status for an entity type."""
    # Get latest pipeline execution for this entity type
    executions = service.list_pipeline_executions(db, entity_type_id=entity_type_id, page=1, page_size=1)
    if not executions:
        raise HTTPException(status_code=404, detail=f"No provisioning found for entity type '{entity_type_id}'")

    latest = executions[0]
    return PipelineStatusResponse(
        id=latest.id,
        status=latest.status,
        current_step=latest.current_step,
        checkpoints=latest.checkpoints,
        error=latest.error,
        progress_percent=100 if latest.status == "completed" else 50 if latest.status == "running" else 0,
    )


# ─── Search / Discovery ────────────────────────────────────────────


@router.get("/search", response_model=EntityTypeListResponse)
async def search_entity_types(
    q: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Page size"),
    db: Session = Depends(get_db_session),
):
    """Search entity types by query."""
    items, total = service.list_entity_types(
        db, category=category, status=status, search=q, page=page, page_size=page_size
    )
    return EntityTypeListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/categories", response_model=list[str])
async def list_categories(
    db: Session = Depends(get_db_session),
):
    """List all unique categories."""
    from sqlalchemy import select, distinct
    from common_lib.modules.app_builder.entity_registry.models import EntityTypeDefinitionRecord

    categories = db.execute(
        select(distinct(EntityTypeDefinitionRecord.category))
        .where(EntityTypeDefinitionRecord.status == "active")
    ).scalars().all()
    return sorted([c for c in categories if c])


@router.get("/stats", response_model=dict)
async def get_registry_stats(
    db: Session = Depends(get_db_session),
):
    """Get registry statistics."""
    from sqlalchemy import select, func
    from common_lib.modules.app_builder.entity_registry.models import EntityTypeDefinitionRecord, EntityInstanceRecord, PipelineExecutionRecord

    total_types = db.execute(select(func.count(EntityTypeDefinitionRecord.id))).scalar() or 0
    active_types = db.execute(
        select(func.count(EntityTypeDefinitionRecord.id)).where(EntityTypeDefinitionRecord.status == "active")
    ).scalar() or 0
    total_instances = db.execute(select(func.count(EntityInstanceRecord.id))).scalar() or 0
    total_pipelines = db.execute(select(func.count(PipelineExecutionRecord.id))).scalar() or 0
    running_pipelines = db.execute(
        select(func.count(PipelineExecutionRecord.id)).where(PipelineExecutionRecord.status == "running")
    ).scalar() or 0

    # Category breakdown
    categories = db.execute(
        select(EntityTypeDefinitionRecord.category, func.count(EntityTypeDefinitionRecord.id))
        .where(EntityTypeDefinitionRecord.status == "active")
        .group_by(EntityTypeDefinitionRecord.category)
    ).all()
    category_counts = {cat: count for cat, count in categories}

    return {
        "entity_types": {
            "total": total_types,
            "active": active_types,
            "by_category": category_counts,
        },
        "instances": {
            "total": total_instances,
        },
        "pipelines": {
            "total": total_pipelines,
            "running": running_pipelines,
        },
    }