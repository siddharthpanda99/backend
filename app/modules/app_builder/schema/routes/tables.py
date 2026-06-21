"""
Schema Builder — Tables CRUD Routes

/api/v1/schema/tables — full CRUD for table definitions
Each table has a name, columns (JSON array), and constraints.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import (
    SchemaService, TableCreate, TableUpdate, TableResponse, TableListResponse,
    ColumnDef, ColumnCreate, ColumnUpdate, APIResponse
)
from common_lib.modules.exceptions import NotFoundError, ConflictError, BadRequestError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tables", tags=["Schema Tables"])
service = SchemaService()


@router.get("/", response_model=TableListResponse)
async def list_tables(
    schema_id: str = Query("default"),
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    items, total = service.list_tables(
        db, schema_id=schema_id, search=search, offset=offset, limit=limit
    )
    return TableListResponse(
        items=[TableResponse.model_validate(t) for t in items],
        total=total,
    )


@router.get("/{table_id}", response_model=TableResponse)
async def get_table(
    table_id: str,
    db: Session = Depends(get_session),
):
    table = service.get_table(db, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    return TableResponse.model_validate(table)


@router.post("/", response_model=TableResponse, status_code=201)
async def create_table(
    data: TableCreate,
    db: Session = Depends(get_session),
):
    try:
        table = service.create_table(db, data)
        logger.info(f"Created table '{table.name}' (id={table.id})")
        return TableResponse.model_validate(table)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: str,
    data: TableUpdate,
    db: Session = Depends(get_session),
):
    try:
        table = service.update_table(db, table_id, data)
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        logger.info(f"Updated table '{table.name}' (id={table.id})")
        return TableResponse.model_validate(table)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{table_id}", response_model=APIResponse)
async def delete_table(
    table_id: str,
    db: Session = Depends(get_session),
):
    table = service.get_table(db, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    name = table.name
    service.delete_table(db, table_id)
    logger.info(f"Deleted table '{name}' (id={table_id})")
    return APIResponse(success=True, message=f"Table '{name}' deleted")


# ─── Column Sub-resource Routes ────────────────────────────────────


@router.get("/{table_id}/columns", response_model=List[ColumnDef])
async def list_columns(
    table_id: str,
    db: Session = Depends(get_session),
):
    try:
        cols = service.list_columns(db, table_id)
        return [ColumnDef(**c) for c in cols]
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{table_id}/columns", response_model=List[ColumnDef], status_code=201)
async def add_column(
    table_id: str,
    data: ColumnCreate,
    db: Session = Depends(get_session),
):
    try:
        cols = service.add_column(db, table_id, data)
        return [ColumnDef(**c) for c in cols]
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/{table_id}/columns/{column_name}", response_model=List[ColumnDef])
async def update_column(
    table_id: str,
    column_name: str,
    data: ColumnUpdate,
    db: Session = Depends(get_session),
):
    try:
        cols = service.update_column(db, table_id, column_name, data)
        return [ColumnDef(**c) for c in cols]
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{table_id}/columns/{column_name}", response_model=List[ColumnDef])
async def delete_column(
    table_id: str,
    column_name: str,
    db: Session = Depends(get_session),
):
    try:
        cols = service.delete_column(db, table_id, column_name)
        return [ColumnDef(**c) for c in cols]
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
