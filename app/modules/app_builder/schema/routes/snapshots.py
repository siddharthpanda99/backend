"""Schema Builder — Snapshot CRUD Routes (#11)"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import SchemaService
from common_lib.modules.exceptions import NotFoundError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/snapshots", tags=["Schema Snapshots"])
service = SchemaService()


def _format_snapshot(s):
    d = s.model_dump()
    d["tables"] = d.pop("tables_json", [])
    d["relationships"] = d.pop("relationships_json", [])
    d["meta"] = d.pop("meta_json", {})
    return d


@router.get("/")
async def list_snapshots(
    schema_id: str = Query("default"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    items, total = service.list_snapshots(
        db, schema_id=schema_id, offset=offset, limit=limit
    )
    result = [_format_snapshot(s) for s in items]
    return {"items": result, "total": total}


@router.get("/{snapshot_id}")
async def get_snapshot(snapshot_id: str, db: Session = Depends(get_session)):
    s = service.get_snapshot(db, snapshot_id)
    if not s:
        raise HTTPException(404, detail="Snapshot not found")
    return _format_snapshot(s)


@router.post("/", status_code=201)
async def create_snapshot(data: dict, db: Session = Depends(get_session)):
    record = service.save_snapshot(db, None, data)
    return _format_snapshot(record)


@router.put("/{snapshot_id}")
async def update_snapshot(snapshot_id: str, data: dict, db: Session = Depends(get_session)):
    try:
        record = service.save_snapshot(db, snapshot_id, data)
        return _format_snapshot(record)
    except NotFoundError:
        raise HTTPException(404, detail="Snapshot not found")


@router.delete("/{snapshot_id}")
async def delete_snapshot(snapshot_id: str, db: Session = Depends(get_session)):
    s = service.get_snapshot(db, snapshot_id)
    if not s:
        raise HTTPException(404, detail="Snapshot not found")
    name = s.name
    service.delete_snapshot(db, snapshot_id)
    return {"success": True, "message": f"Snapshot '{name}' deleted"}
