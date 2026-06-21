"""
Schema Builder — Relationships CRUD Routes

/api/v1/schema/relationships — full CRUD for foreign key relationships
Supports one_to_one, one_to_many, many_to_many with cascade rules.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import (
    SchemaService, RelationshipCreate, RelationshipUpdate, RelationshipResponse,
    RelationshipListResponse, APIResponse
)
from common_lib.modules.exceptions import NotFoundError, ConflictError, BadRequestError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/relationships", tags=["Schema Relationships"])
service = SchemaService()


@router.get("/", response_model=RelationshipListResponse)
async def list_relationships(
    schema_id: str = Query("default"),
    source_table_id: Optional[str] = Query(None),
    target_table_id: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    items, total = service.list_relationships(
        db, schema_id=schema_id, source_table_id=source_table_id,
        target_table_id=target_table_id, offset=offset, limit=limit
    )
    return RelationshipListResponse(
        items=[RelationshipResponse.model_validate(r) for r in items],
        total=total,
    )


@router.get("/{rel_id}", response_model=RelationshipResponse)
async def get_relationship(
    rel_id: str,
    db: Session = Depends(get_session),
):
    rel = service.get_relationship(db, rel_id)
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return RelationshipResponse.model_validate(rel)


@router.post("/", response_model=RelationshipResponse, status_code=201)
async def create_relationship(
    data: RelationshipCreate,
    db: Session = Depends(get_session),
):
    try:
        rel = service.create_relationship(db, data)
        logger.info(f"Created relationship '{rel.name}' ({rel.relation_type})")
        return RelationshipResponse.model_validate(rel)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{rel_id}", response_model=RelationshipResponse)
async def update_relationship(
    rel_id: str,
    data: RelationshipUpdate,
    db: Session = Depends(get_session),
):
    rel = service.update_relationship(db, rel_id, data)
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
    logger.info(f"Updated relationship '{rel.name}' (id={rel.id})")
    return RelationshipResponse.model_validate(rel)


@router.delete("/{rel_id}", response_model=APIResponse)
async def delete_relationship(
    rel_id: str,
    db: Session = Depends(get_session),
):
    rel = service.get_relationship(db, rel_id)
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
    name = rel.name
    service.delete_relationship(db, rel_id)
    logger.info(f"Deleted relationship '{name}' (id={rel_id})")
    return APIResponse(success=True, message=f"Relationship '{name}' deleted")
