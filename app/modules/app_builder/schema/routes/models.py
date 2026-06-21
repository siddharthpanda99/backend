"""Schema Builder — Model Definition CRUD Routes (#10)"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import SchemaService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/models/definitions", tags=["Schema Models"])
service = SchemaService()


@router.get("/")
async def list_models(
    schema_id: str = Query("default"),
    language: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    items, total = service.list_models(
        db, schema_id=schema_id, language=language, offset=offset, limit=limit
    )
    return {"items": [m.model_dump() for m in items], "total": total}


@router.get("/{model_id}")
async def get_model(model_id: str, db: Session = Depends(get_session)):
    m = service.get_model(db, model_id)
    if not m:
        raise HTTPException(404, detail="Model not found")
    return m.model_dump()


@router.post("/", status_code=201)
async def create_model(data: dict, db: Session = Depends(get_session)):
    record = service.create_model(db, data)
    return record.model_dump()


@router.put("/{model_id}")
async def update_model(model_id: str, data: dict, db: Session = Depends(get_session)):
    m = service.update_model(db, model_id, data)
    if not m:
        raise HTTPException(404, detail="Model not found")
    return m.model_dump()


@router.delete("/{model_id}")
async def delete_model(model_id: str, db: Session = Depends(get_session)):
    m = service.delete_model(db, model_id)
    if not m:
        raise HTTPException(404, detail="Model not found")
    return {"success": True, "message": f"Model '{m.name}' deleted"}
