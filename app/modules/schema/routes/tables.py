"""
Schema Builder — Tables CRUD Routes

/api/v1/schema/tables — full CRUD for table definitions
Each table has a name, columns (JSON array), and constraints.
"""

import uuid
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from common_lib.modules.data_storage.database.connection import get_session
from ..models import SchemaTableRecord
from ..schemas import (
    TableCreate, TableUpdate, TableResponse, TableListResponse,
    ColumnDef, ColumnCreate, ColumnUpdate, APIResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tables", tags=["Schema Tables"])


@router.get("/", response_model=TableListResponse)
async def list_tables(
    schema_id: str = Query("default"),
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    query = select(SchemaTableRecord).where(
        SchemaTableRecord.schema_id == schema_id
    ).order_by(SchemaTableRecord.created_at)

    if search:
        query = query.where(SchemaTableRecord.name.ilike(f"%{search}%"))

    total = len(db.execute(query).scalars().all())
    items = db.execute(query.offset(offset).limit(limit)).scalars().all()

    return TableListResponse(
        items=[TableResponse.model_validate(t) for t in items],
        total=total,
    )


@router.get("/{table_id}", response_model=TableResponse)
async def get_table(
    table_id: str,
    db: Session = Depends(get_session),
):
    table = db.execute(
        select(SchemaTableRecord).where(SchemaTableRecord.id == table_id)
    ).scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    return TableResponse.model_validate(table)


@router.post("/", response_model=TableResponse, status_code=201)
async def create_table(
    data: TableCreate,
    db: Session = Depends(get_session),
):
    # Check for duplicate name within schema
    existing = db.execute(
        select(SchemaTableRecord).where(
            SchemaTableRecord.schema_id == data.schema_id,
            SchemaTableRecord.name == data.name,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Table '{data.name}' already exists")

    table = SchemaTableRecord(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        schema_id=data.schema_id,
        columns=[c.model_dump() for c in data.columns] if data.columns else [],
        constraints=data.constraints.model_dump() if data.constraints else None,
    )
    db.add(table)
    db.commit()
    db.refresh(table)
    logger.info(f"Created table '{table.name}' (id={table.id})")
    return TableResponse.model_validate(table)


@router.put("/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: str,
    data: TableUpdate,
    db: Session = Depends(get_session),
):
    table = db.execute(
        select(SchemaTableRecord).where(SchemaTableRecord.id == table_id)
    ).scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    if data.name is not None:
        # Check for name conflict with other tables in same schema
        conflict = db.execute(
            select(SchemaTableRecord).where(
                SchemaTableRecord.schema_id == table.schema_id,
                SchemaTableRecord.name == data.name,
                SchemaTableRecord.id != table_id,
            )
        ).scalar_one_or_none()
        if conflict:
            raise HTTPException(status_code=409, detail=f"Table name '{data.name}' already taken")
        table.name = data.name
    if data.description is not None:
        table.description = data.description
    if data.columns is not None:
        table.columns = [c.model_dump() for c in data.columns]
    if data.constraints is not None:
        table.constraints = data.constraints.model_dump()

    db.commit()
    db.refresh(table)
    logger.info(f"Updated table '{table.name}' (id={table.id})")
    return TableResponse.model_validate(table)


@router.delete("/{table_id}", response_model=APIResponse)
async def delete_table(
    table_id: str,
    db: Session = Depends(get_session),
):
    table = db.execute(
        select(SchemaTableRecord).where(SchemaTableRecord.id == table_id)
    ).scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    # Delete related relationships first
    from ..models import SchemaRelationshipRecord
    from sqlalchemy import delete as sql_delete
    db.execute(
        sql_delete(SchemaRelationshipRecord).where(
            (SchemaRelationshipRecord.source_table_id == table_id) |
            (SchemaRelationshipRecord.target_table_id == table_id)
        )
    )

    db.delete(table)
    db.commit()
    logger.info(f"Deleted table '{table.name}' (id={table.id})")
    return APIResponse(success=True, message=f"Table '{table.name}' deleted")


# ─── Column Sub-resource Routes ────────────────────────────────────


@router.get("/{table_id}/columns", response_model=List[ColumnDef])
async def list_columns(
    table_id: str,
    db: Session = Depends(get_session),
):
    table = db.execute(
        select(SchemaTableRecord).where(SchemaTableRecord.id == table_id)
    ).scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    return [ColumnDef(**c) for c in (table.columns or [])]


@router.post("/{table_id}/columns", response_model=List[ColumnDef], status_code=201)
async def add_column(
    table_id: str,
    data: ColumnCreate,
    db: Session = Depends(get_session),
):
    table = db.execute(
        select(SchemaTableRecord).where(SchemaTableRecord.id == table_id)
    ).scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    columns = table.columns or []
    # Check for duplicate column name
    for col in columns:
        if col.get("name") == data.column.name:
            raise HTTPException(
                status_code=409,
                detail=f"Column '{data.column.name}' already exists in table '{table.name}'",
            )

    columns.append(data.column.model_dump())
    table.columns = columns
    db.commit()
    db.refresh(table)
    return [ColumnDef(**c) for c in (table.columns or [])]


@router.put("/{table_id}/columns/{column_name}", response_model=List[ColumnDef])
async def update_column(
    table_id: str,
    column_name: str,
    data: ColumnUpdate,
    db: Session = Depends(get_session),
):
    table = db.execute(
        select(SchemaTableRecord).where(SchemaTableRecord.id == table_id)
    ).scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    columns = table.columns or []
    found = False
    for i, col in enumerate(columns):
        if col.get("name") == column_name:
            columns[i] = data.column.model_dump()
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail=f"Column '{column_name}' not found")

    # If renaming, check for duplicates
    if data.column.name != column_name:
        for col in columns:
            if col.get("name") == data.column.name and col != data.column.model_dump():
                raise HTTPException(
                    status_code=409,
                    detail=f"Column name '{data.column.name}' already exists",
                )

    table.columns = columns
    db.commit()
    db.refresh(table)
    return [ColumnDef(**c) for c in (table.columns or [])]


@router.delete("/{table_id}/columns/{column_name}", response_model=List[ColumnDef])
async def delete_column(
    table_id: str,
    column_name: str,
    db: Session = Depends(get_session),
):
    table = db.execute(
        select(SchemaTableRecord).where(SchemaTableRecord.id == table_id)
    ).scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    columns = table.columns or []
    new_columns = [c for c in columns if c.get("name") != column_name]
    if len(new_columns) == len(columns):
        raise HTTPException(status_code=404, detail=f"Column '{column_name}' not found")

    table.columns = new_columns
    db.commit()
    db.refresh(table)
    return [ColumnDef(**c) for c in (table.columns or [])]
