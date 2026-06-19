"""
Schema Builder — Relationships CRUD Routes

/api/v1/schema/relationships — full CRUD for foreign key relationships
Supports one_to_one, one_to_many, many_to_many with cascade rules.
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from common_lib.modules.data_storage.database.connection import get_session
from ..models import SchemaRelationshipRecord, SchemaTableRecord
from ..schemas import (
    RelationshipCreate, RelationshipUpdate, RelationshipResponse,
    RelationshipListResponse, APIResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/relationships", tags=["Schema Relationships"])


@router.get("/", response_model=RelationshipListResponse)
async def list_relationships(
    schema_id: str = Query("default"),
    source_table_id: Optional[str] = Query(None),
    target_table_id: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    query = select(SchemaRelationshipRecord).where(
        SchemaRelationshipRecord.schema_id == schema_id
    ).order_by(SchemaRelationshipRecord.created_at)

    if source_table_id:
        query = query.where(SchemaRelationshipRecord.source_table_id == source_table_id)
    if target_table_id:
        query = query.where(SchemaRelationshipRecord.target_table_id == target_table_id)

    total = len(db.execute(query).scalars().all())
    items = db.execute(query.offset(offset).limit(limit)).scalars().all()

    return RelationshipListResponse(
        items=[RelationshipResponse.model_validate(r) for r in items],
        total=total,
    )


@router.get("/{rel_id}", response_model=RelationshipResponse)
async def get_relationship(
    rel_id: str,
    db: Session = Depends(get_session),
):
    rel = db.execute(
        select(SchemaRelationshipRecord).where(SchemaRelationshipRecord.id == rel_id)
    ).scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return RelationshipResponse.model_validate(rel)


@router.post("/", response_model=RelationshipResponse, status_code=201)
async def create_relationship(
    data: RelationshipCreate,
    db: Session = Depends(get_session),
):
    # Validate source and target tables exist
    source = db.execute(
        select(SchemaTableRecord).where(SchemaTableRecord.id == data.source_table_id)
    ).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f"Source table '{data.source_table_id}' not found")

    target = db.execute(
        select(SchemaTableRecord).where(SchemaTableRecord.id == data.target_table_id)
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail=f"Target table '{data.target_table_id}' not found")

    # Validate column names exist in their respective tables
    source_cols = [c.get("name") for c in (source.columns or [])]
    if data.source_column not in source_cols:
        raise HTTPException(
            status_code=400,
            detail=f"Column '{data.source_column}' not found in table '{source.name}'",
        )

    target_cols = [c.get("name") for c in (target.columns or [])]
    if data.target_column not in target_cols:
        raise HTTPException(
            status_code=400,
            detail=f"Column '{data.target_column}' not found in table '{target.name}'",
        )

    # For M:N, validate through_table is provided
    if data.relation_type == "many_to_many" and not data.through_table:
        raise HTTPException(
            status_code=400,
            detail="Many-to-many relationships require a 'through_table' name",
        )

    rel = SchemaRelationshipRecord(
        id=str(uuid.uuid4()),
        name=data.name,
        schema_id=data.schema_id,
        relation_type=data.relation_type,
        source_table_id=data.source_table_id,
        source_column=data.source_column,
        target_table_id=data.target_table_id,
        target_column=data.target_column,
        on_delete=data.on_delete,
        on_update=data.on_update,
        through_table=data.through_table,
        inverse_name=data.inverse_name,
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    logger.info(f"Created relationship '{rel.name}' ({rel.relation_type})")
    return RelationshipResponse.model_validate(rel)


@router.put("/{rel_id}", response_model=RelationshipResponse)
async def update_relationship(
    rel_id: str,
    data: RelationshipUpdate,
    db: Session = Depends(get_session),
):
    rel = db.execute(
        select(SchemaRelationshipRecord).where(SchemaRelationshipRecord.id == rel_id)
    ).scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(rel, key, value)

    db.commit()
    db.refresh(rel)
    logger.info(f"Updated relationship '{rel.name}' (id={rel.id})")
    return RelationshipResponse.model_validate(rel)


@router.delete("/{rel_id}", response_model=APIResponse)
async def delete_relationship(
    rel_id: str,
    db: Session = Depends(get_session),
):
    rel = db.execute(
        select(SchemaRelationshipRecord).where(SchemaRelationshipRecord.id == rel_id)
    ).scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")

    db.delete(rel)
    db.commit()
    logger.info(f"Deleted relationship '{rel.name}' (id={rel.id})")
    return APIResponse(success=True, message=f"Relationship '{rel.name}' deleted")
