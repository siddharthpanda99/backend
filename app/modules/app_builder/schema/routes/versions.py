"""Schema Builder — Version History Routes (#8)"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import SchemaService
from common_lib.modules.exceptions import NotFoundError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/versions", tags=["Schema Versions"])
service = SchemaService()


@router.get("/")
async def list_versions(schema_id: str = Query("default"), db: Session = Depends(get_session)):
    items = service.list_versions(db, schema_id=schema_id)
    return {"items": [v.model_dump() for v in items], "total": len(items)}


@router.get("/{version_id}")
async def get_version(version_id: str, db: Session = Depends(get_session)):
    v = service.get_version(db, version_id)
    if not v:
        raise HTTPException(404, detail="Version not found")
    return v.model_dump()


@router.post("/", status_code=201)
async def create_version(data: dict, db: Session = Depends(get_session)):
    record = service.save_version(db, None, data)
    return record.model_dump()


@router.delete("/{version_id}")
async def delete_version(version_id: str, db: Session = Depends(get_session)):
    v = service.delete_version(db, version_id)
    if not v:
        raise HTTPException(404, detail="Version not found")
    return {"success": True, "message": f"Version '{v.label}' deleted"}


@router.post("/{version_id}/diff")
async def diff_version(version_id: str, db: Session = Depends(get_session)):
    """Compute diff between this version's snapshot and the current snapshot."""
    diff_res = service.diff_version(db, version_id)
    if not diff_res:
        raise HTTPException(404, detail="Version not found")
    return diff_res
