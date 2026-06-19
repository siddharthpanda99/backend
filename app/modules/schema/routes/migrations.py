"""
Schema Builder — Migrations CRUD Routes

/api/v1/schema/migrations — full CRUD for migration definitions
Supports execute, rollback, schedule, and status tracking.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from common_lib.modules.data_storage.database.connection import get_session
from ..models import SchemaMigrationRecord
from ..schemas import (
    MigrationCreate, MigrationUpdate, MigrationResponse,
    MigrationListResponse, APIResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/migrations", tags=["Schema Migrations"])


@router.get("/", response_model=MigrationListResponse)
async def list_migrations(
    schema_id: str = Query("default"),
    status: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    query = select(SchemaMigrationRecord).where(
        SchemaMigrationRecord.schema_id == schema_id
    ).order_by(SchemaMigrationRecord.created_at.desc())

    if status:
        query = query.where(SchemaMigrationRecord.status == status)

    total = len(db.execute(query).scalars().all())
    items = db.execute(query.offset(offset).limit(limit)).scalars().all()

    return MigrationListResponse(
        items=[MigrationResponse.model_validate(m) for m in items],
        total=total,
    )


@router.get("/{migration_id}", response_model=MigrationResponse)
async def get_migration(
    migration_id: str,
    db: Session = Depends(get_session),
):
    migration = db.execute(
        select(SchemaMigrationRecord).where(SchemaMigrationRecord.id == migration_id)
    ).scalar_one_or_none()
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found")
    return MigrationResponse.model_validate(migration)


@router.post("/", response_model=MigrationResponse, status_code=201)
async def create_migration(
    data: MigrationCreate,
    db: Session = Depends(get_session),
):
    # Check for duplicate version within schema
    existing = db.execute(
        select(SchemaMigrationRecord).where(
            SchemaMigrationRecord.schema_id == data.schema_id,
            SchemaMigrationRecord.version == data.version,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Migration version '{data.version}' already exists",
        )

    migration = SchemaMigrationRecord(
        id=str(uuid.uuid4()),
        name=data.name,
        schema_id=data.schema_id,
        version=data.version,
        status="pending",
        sql_up=data.sql_up,
        sql_down=data.sql_down,
        diff_summary=data.diff_summary,
    )
    db.add(migration)
    db.commit()
    db.refresh(migration)
    logger.info(f"Created migration '{migration.name}' (v{migration.version})")
    return MigrationResponse.model_validate(migration)


@router.put("/{migration_id}", response_model=MigrationResponse)
async def update_migration(
    migration_id: str,
    data: MigrationUpdate,
    db: Session = Depends(get_session),
):
    migration = db.execute(
        select(SchemaMigrationRecord).where(SchemaMigrationRecord.id == migration_id)
    ).scalar_one_or_none()
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found")

    update_dict = data.model_dump(exclude_unset=True)

    # Handle scheduled_for string → datetime conversion
    if "scheduled_for" in update_dict and update_dict["scheduled_for"]:
        try:
            update_dict["scheduled_for"] = datetime.fromisoformat(
                update_dict["scheduled_for"].replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="Invalid scheduled_for format. Use ISO 8601.")

    for key, value in update_dict.items():
        setattr(migration, key, value)

    db.commit()
    db.refresh(migration)
    logger.info(f"Updated migration '{migration.name}' (status={migration.status})")
    return MigrationResponse.model_validate(migration)


@router.delete("/{migration_id}", response_model=APIResponse)
async def delete_migration(
    migration_id: str,
    db: Session = Depends(get_session),
):
    migration = db.execute(
        select(SchemaMigrationRecord).where(SchemaMigrationRecord.id == migration_id)
    ).scalar_one_or_none()
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found")

    db.delete(migration)
    db.commit()
    logger.info(f"Deleted migration '{migration.name}' (id={migration.id})")
    return APIResponse(success=True, message=f"Migration '{migration.name}' deleted")


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
    migration = db.execute(
        select(SchemaMigrationRecord).where(SchemaMigrationRecord.id == migration_id)
    ).scalar_one_or_none()
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found")

    if migration.status not in ("pending", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"Migration is '{migration.status}', not 'pending' or 'failed'",
        )

    from sqlalchemy import text as sql_text
    from common_lib.modules.data_storage.database.connection import engine
    from sqlalchemy.exc import SQLAlchemyError

    start = datetime.now(timezone.utc)
    try:
        with engine.connect() as conn:
            conn.execute(sql_text(migration.sql_up))
            conn.commit()

        migration.status = "applied"
        migration.executed_at = datetime.now(timezone.utc)
        migration.executed_by = executed_by
        migration.duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        migration.error_message = None
        logger.info(f"Migration '{migration.name}' executed successfully")

    except SQLAlchemyError as e:
        migration.status = "failed"
        migration.error_message = str(e)[:2000]
        migration.duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        logger.error(f"Migration '{migration.name}' failed: {e}")

    db.commit()
    db.refresh(migration)
    return MigrationResponse.model_validate(migration)


@router.post("/{migration_id}/rollback", response_model=MigrationResponse)
async def rollback_migration(
    migration_id: str,
    db: Session = Depends(get_session),
):
    """
    Rollback an applied migration by running its DOWN SQL.
    """
    migration = db.execute(
        select(SchemaMigrationRecord).where(SchemaMigrationRecord.id == migration_id)
    ).scalar_one_or_none()
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found")

    if migration.status != "applied":
        raise HTTPException(
            status_code=400,
            detail=f"Migration is '{migration.status}', not 'applied'",
        )
    if not migration.sql_down:
        raise HTTPException(
            status_code=400,
            detail="Migration has no DOWN SQL defined",
        )

    from sqlalchemy import text as sql_text
    from common_lib.modules.data_storage.database.connection import engine
    from sqlalchemy.exc import SQLAlchemyError

    start = datetime.now(timezone.utc)
    try:
        with engine.connect() as conn:
            conn.execute(sql_text(migration.sql_down))
            conn.commit()

        migration.status = "pending"
        migration.executed_at = None
        migration.duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        migration.error_message = None
        logger.info(f"Migration '{migration.name}' rolled back successfully")

    except SQLAlchemyError as e:
        migration.status = "failed"
        migration.error_message = str(e)[:2000]
        migration.duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        logger.error(f"Migration '{migration.name}' rollback failed: {e}")

    db.commit()
    db.refresh(migration)
    return MigrationResponse.model_validate(migration)
