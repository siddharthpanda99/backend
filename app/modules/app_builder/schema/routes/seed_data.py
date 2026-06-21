"""Schema Builder — Seed Data CRUD Routes (#6)"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import SchemaService
from common_lib.modules.exceptions import NotFoundError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/seed-data", tags=["Schema Seed Data"])
service = SchemaService()


@router.get("/")
async def list_seed_data(
    schema_id: str = Query("default"),
    table_id: Optional[str] = Query(None),
    db: Session = Depends(get_session),
):
    items = service.list_seed_data(db, schema_id=schema_id, table_id=table_id)
    return {"items": [s.model_dump() for s in items], "total": len(items)}


@router.get("/{seed_id}")
async def get_seed_data(seed_id: str, db: Session = Depends(get_session)):
    s = service.get_seed_record(db, seed_id)
    if not s:
        raise HTTPException(404, detail="Seed data not found")
    return s.model_dump()


@router.post("/", status_code=201)
async def create_seed_data(data: dict, db: Session = Depends(get_session)):
    record = service.save_seed_record(db, None, data)
    return record.model_dump()


@router.put("/{seed_id}")
async def update_seed_data(seed_id: str, data: dict, db: Session = Depends(get_session)):
    try:
        record = service.save_seed_record(db, seed_id, data)
        return record.model_dump()
    except NotFoundError:
        raise HTTPException(404, detail="Seed data not found")


@router.delete("/{seed_id}")
async def delete_seed_data(seed_id: str, db: Session = Depends(get_session)):
    success = service.delete_seed_data_record(db, seed_id)
    if not success:
        raise HTTPException(404, detail="Seed data not found")
    return {"success": True, "message": "Seed data deleted"}
