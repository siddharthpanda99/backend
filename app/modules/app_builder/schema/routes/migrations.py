"""
Schema Builder — Migrations CRUD Routes

/api/v1/schema/migrations — full CRUD for migration definitions
Supports execute, rollback, schedule, and status tracking.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session, engine
from common_lib.modules.app_builder.schema import (
    SchemaService, MigrationCreate, MigrationUpdate, MigrationResponse,
    MigrationListResponse, APIResponse
)
from common_lib.modules.exceptions import NotFoundError, ConflictError, BadRequestError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/migrations", tags=["Schema Migrations"])
service = SchemaService()


@router.get("/", response_model=MigrationListResponse)
async def list_migrations(
    schema_id: str = Query("default"),
    status: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    items, total = service.list_migrations(
        db, schema_id=schema_id, status=status, offset=offset, limit=limit
    )
    return MigrationListResponse(
        items=[MigrationResponse.model_validate(m) for m in items],
        total=total,
    )


@router.get("/{migration_id}", response_model=MigrationResponse)
async def get_migration(
    migration_id: str,
    db: Session = Depends(get_session),
):
    migration = service.get_migration(db, migration_id)
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found")
    return MigrationResponse.model_validate(migration)


@router.post("/", response_model=MigrationResponse, status_code=201)
async def create_migration(
    data: MigrationCreate,
    db: Session = Depends(get_session),
):
    try:
        migration = service.create_migration(db, data)
        logger.info(f"Created migration '{migration.name}' (v{migration.version})")
        return MigrationResponse.model_validate(migration)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/{migration_id}", response_model=MigrationResponse)
async def update_migration(
    migration_id: str,
    data: MigrationUpdate,
    db: Session = Depends(get_session),
):
    try:
        migration = service.update_migration(db, migration_id, data)
        if not migration:
            raise HTTPException(status_code=404, detail="Migration not found")
        logger.info(f"Updated migration '{migration.name}' (status={migration.status})")
        return MigrationResponse.model_validate(migration)
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{migration_id}", response_model=APIResponse)
async def delete_migration(
    migration_id: str,
    db: Session = Depends(get_session),
):
    migration = service.get_migration(db, migration_id)
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found")
    name = migration.name
    service.delete_migration(db, migration_id)
    logger.info(f"Deleted migration '{name}' (id={migration_id})")
    return APIResponse(success=True, message=f"Migration '{name}' deleted")


# ─── Execute / Rollback / Schedule ─────────────────────────────────


@router.post("/{migration_id}/execute", response_model=MigrationResponse)
async def execute_migration(
    migration_id: str,
    executed_by: str = "system",
    db: Session = Depends(get_session),
):
    """
    Execute a pending migration. Attempts to run the UP SQL against the
    connected database. Records success/failure and duration.
    """
    try:
        migration = service.execute_migration_on_engine(db, migration_id, engine, executed_by=executed_by)
        return MigrationResponse.model_validate(migration)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{migration_id}/rollback", response_model=MigrationResponse)
async def rollback_migration(
    migration_id: str,
    db: Session = Depends(get_session),
):
    """
    Rollback an applied migration by running its DOWN SQL.
    """
    try:
        migration = service.rollback_migration_on_engine(db, migration_id, engine)
        return MigrationResponse.model_validate(migration)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
