"""Schema Builder — ERD Diagram Layout Persistence Routes (#7)"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import SchemaService
from common_lib.modules.exceptions import NotFoundError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diagram-layouts", tags=["Schema Diagram"])
service = SchemaService()


def _format_layout(l):
    d = l.model_dump()
    d["nodes"] = d.pop("nodes_json", [])
    d["edges"] = d.pop("edges_json", [])
    d["viewport"] = d.pop("viewport_json", {})
    return d


@router.get("/")
async def list_layouts(schema_id: str = Query("default"), db: Session = Depends(get_session)):
    items = service.list_diagram_layouts(db, schema_id)
    result = [_format_layout(l) for l in items]
    return {"items": result, "total": len(result)}


@router.get("/{layout_id}")
async def get_layout(layout_id: str, db: Session = Depends(get_session)):
    l = service.get_diagram_layout_by_id(db, layout_id)
    if not l:
        raise HTTPException(404, detail="Layout not found")
    return _format_layout(l)


@router.post("/", status_code=201)
async def save_layout(data: dict, db: Session = Depends(get_session)):
    record = service.save_diagram_layout_record(db, None, data)
    return _format_layout(record)


@router.put("/{layout_id}")
async def update_layout(layout_id: str, data: dict, db: Session = Depends(get_session)):
    try:
        record = service.save_diagram_layout_record(db, layout_id, data)
        return _format_layout(record)
    except NotFoundError:
        raise HTTPException(404, detail="Layout not found")


@router.delete("/{layout_id}")
async def delete_layout(layout_id: str, db: Session = Depends(get_session)):
    success = service.delete_diagram_layout_record(db, layout_id)
    if not success:
        raise HTTPException(404, detail="Layout not found")
    return {"success": True, "message": "Layout deleted"}
