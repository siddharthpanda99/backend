import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from common_lib.modules.image_processing.functions.text.dynamic_engine.models import (
    WildcardRecord,
)
from common_lib.modules.data_storage.database.connection import (
    get_session,
    _get_db_service,
)
from common_lib.modules.wildcards.service import WildcardService
from common_lib.modules.vision.schemas import (
    WildcardRecordSchema,
    WildcardListResponse,
    WildcardCreateRequest,
    WildcardUpdateRequest,
)
from common_lib.modules.data_storage.database.repository import NotFoundError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wildcards", tags=["Wildcards"])
_svc = WildcardService()


class WildcardPreviewRequest(BaseModel):
    name: str
    content: str


class WildcardSaveRequest(BaseModel):
    name: str
    values: List[str]


@router.get("/", response_model=WildcardListResponse)
async def list_wildcards(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    offset: int = Query(0),
    limit: int = Query(50),
    skip: Optional[int] = Query(None),
):
    final_offset = offset if skip is None else skip
    with next(get_session()) as session:
        results, total, categories = _svc.list_wildcards(
            session,
            search=search,
            category=category,
            offset=final_offset,
            limit=limit,
        )
        return WildcardListResponse(
            items=[WildcardRecordSchema.from_orm(r) for r in results],
            total=total,
            categories=categories,
        )


@router.get("/stats")
async def get_wildcard_stats():
    with next(get_session()) as session:
        stats = _svc.get_stats(session)
        return {"status": "success", "data": stats}


@router.post("/sync")
async def sync_wildcards(force: bool = Query(False)):
    db_service = _get_db_service()
    with db_service.get_session() as session:
        try:
            results = _svc.sync(session, force=force)
            session.commit()
            return {"status": "success", "data": results}
        except Exception as e:
            logger.error(f"Wildcard sync failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview")
async def preview_wildcard_content(request: WildcardPreviewRequest):
    try:
        data = _svc.preview_content(request.name, request.content)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse content: {e}")


@router.post("/", response_model=WildcardRecordSchema)
@router.post("/save", response_model=WildcardRecordSchema)
async def save_wildcard(request: WildcardCreateRequest):
    with next(get_session()) as session:
        record = _svc.create_wildcard(
            session,
            name=request.name,
            values=request.values,
            category=request.category,
            description=request.description,
        )
        return WildcardRecordSchema.from_orm(record)


@router.put("/{wildcard_id}", response_model=WildcardRecordSchema)
async def update_wildcard(wildcard_id: int, request: WildcardUpdateRequest):
    with next(get_session()) as session:
        try:
            record = _svc.update_wildcard(
                session,
                wildcard_id=wildcard_id,
                name=request.name,
                values=request.values,
                category=request.category,
                description=request.description,
            )
            return WildcardRecordSchema.from_orm(record)
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Wildcard not found")


@router.get("/sample")
async def get_wildcard_samples():
    return {
        "status": "success",
        "data": {
            "content": "Entry 1\nEntry 2\nEntry 3\n# Comments are supported\nEntry 4",
            "yaml": 'my_custom_wildcard:\n  description: "Optional description"\n  values:\n    - "Value 1"\n    - "Value 2"\n    - "weight::Value with weight"',
        },
    }


@router.get("/{wildcard_id}", response_model=WildcardRecordSchema)
async def get_wildcard(wildcard_id: int):
    with next(get_session()) as session:
        try:
            record = _svc.get_wildcard(session, wildcard_id)
            return WildcardRecordSchema.from_orm(record)
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Wildcard not found")


@router.delete("/{wildcard_id}")
async def delete_wildcard(wildcard_id: int):
    with next(get_session()) as session:
        try:
            _svc.delete_wildcard(session, wildcard_id)
            return {"status": "success", "message": "Wildcard deleted"}
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Wildcard not found")
