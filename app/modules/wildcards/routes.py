import os
import logging
import yaml
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Body
from sqlalchemy import or_, func
from sqlmodel import select
from pydantic import BaseModel

from common_lib.modules.image_processing.functions.text.dynamic_engine.models import (
    WildcardRecord,
)
from common_lib.modules.data_storage.database.connection import (
    get_session,
    _get_db_service,
)

from app.modules.wildcards.service import WildcardService
from common_lib.modules.vision.schemas import (
    WildcardRecordSchema,
    WildcardListResponse,
    WildcardCreateRequest,
    WildcardUpdateRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wildcards", tags=["Wildcards"])


# --- Local Request Schemas for Consistency ---
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
    skip: Optional[int] = Query(None),  # Legacy support
):
    """
    List wildcards. Matches the skip/limit expected by the industrialized client.
    """
    # Normalize skip/offset
    final_offset = offset if skip is None else skip

    with next(get_session()) as session:
        # Build base statement for items
        stmt = select(WildcardRecord)

        # Build count statement
        count_stmt = select(func.count()).select_from(WildcardRecord)

        if search:
            filter_expr = or_(
                WildcardRecord.name.ilike(f"%{search}%"),
                WildcardRecord.description.ilike(f"%{search}%"),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        if category:
            stmt = stmt.where(WildcardRecord.category == category)
            count_stmt = count_stmt.where(WildcardRecord.category == category)

        # Get total count
        total = session.execute(count_stmt).scalar()

        # Get unique categories
        categories_stmt = select(WildcardRecord.category).distinct()
        categories = session.execute(categories_stmt).scalars().all()
        categories = [c for c in categories if c]

        # Paginate and fetch results
        stmt = stmt.offset(final_offset).limit(limit)
        results = session.execute(stmt).scalars().all()

        return WildcardListResponse(
            items=[WildcardRecordSchema.from_orm(r) for r in results],
            total=total,
            categories=categories,
        )


@router.get("/stats")
async def get_wildcard_stats():
    """
    Get statistics about the wildcard library.
    """
    with next(get_session()) as session:
        service = WildcardService()
        stats = service.get_stats(session)

        return {"status": "success", "data": stats}


@router.post("/sync")
async def sync_wildcards(
    force: bool = Query(False),
):
    """
    Sync all wildcards from filesystem to database.
    Scans: Resources/wildcards/* (collections/, nsfw/, and root YAML files)
    """
    db_service = _get_db_service()
    with db_service.get_session() as session:
        service = WildcardService()
        try:
            results = service.sync(session, force=force)
            session.commit()
            logger.info("Wildcard sync completed successfully")

            return {"status": "success", "data": results}
        except Exception as e:
            logger.error(f"Wildcard sync failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview")
async def preview_wildcard_content(request: WildcardPreviewRequest):
    """
    Parse raw wildcard content and return a preview.
    Matches the JSON body expected by the industrialized client.
    """
    try:
        content = request.content
        if content.strip().startswith("-") or ":" in content:
            # Likely YAML
            try:
                data = yaml.safe_load(content)
                if isinstance(data, list):
                    values = data
                elif isinstance(data, dict):
                    # Pick the first list found in dict or keys
                    values = next(
                        (v for v in data.values() if isinstance(v, list)),
                        list(data.keys()),
                    )
                else:
                    values = [str(data)]
            except:
                values = [
                    l.strip()
                    for l in content.splitlines()
                    if l.strip() and not l.startswith("#")
                ]
        else:
            values = [
                l.strip()
                for l in content.splitlines()
                if l.strip() and not l.startswith("#")
            ]

        return {
            "status": "success",
            "data": {"name": request.name, "values": values, "count": len(values)},
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse content: {e}")


@router.post("/", response_model=WildcardRecordSchema)
@router.post("/save", response_model=WildcardRecordSchema)
async def save_wildcard(request: WildcardCreateRequest):
    """
    Save a wildcard to the database. Supports both POST / and POST /save.
    """
    with next(get_session()) as session:
        # Check if exists
        stmt = select(WildcardRecord).where(WildcardRecord.name == request.name)
        record = session.execute(stmt).scalar_one_or_none()

        if record:
            if request.values is not None:
                record.values = request.values
            if request.category:
                record.category = request.category
            elif "/" in request.name:
                record.category = request.name.split("/")[0]

            if request.description:
                record.description = request.description
        else:
            record = WildcardRecord(
                name=request.name,
                values=request.values,
                category=request.category
                or (request.name.split("/")[0] if "/" in request.name else "custom"),
                description=request.description or "User defined wildcard",
            )

        session.add(record)
        session.commit()
        session.refresh(record)

        return WildcardRecordSchema.from_orm(record)


@router.put("/{wildcard_id}", response_model=WildcardRecordSchema)
async def update_wildcard(wildcard_id: int, request: WildcardUpdateRequest):
    """
    Update an existing wildcard record.
    """
    with next(get_session()) as session:
        record = session.get(WildcardRecord, wildcard_id)
        if not record:
            raise HTTPException(status_code=404, detail="Wildcard not found")

        if request.name is not None:
            record.name = request.name
        if request.values is not None:
            record.values = request.values
        if request.category is not None:
            record.category = request.category
        if request.description is not None:
            record.description = request.description

        session.add(record)
        session.commit()
        session.refresh(record)

        return WildcardRecordSchema.from_orm(record)


@router.get("/sample")
async def get_wildcard_samples():
    """Get sample wildcard file formats."""
    return {
        "status": "success",
        "data": {
            "content": "Entry 1\nEntry 2\nEntry 3\n# Comments are supported\nEntry 4",
            "yaml": 'my_custom_wildcard:\n  description: "Optional description"\n  values:\n    - "Value 1"\n    - "Value 2"\n    - "weight::Value with weight"',
        },
    }


@router.get("/{wildcard_id}", response_model=WildcardRecordSchema)
async def get_wildcard(wildcard_id: int):
    """Get a single wildcard record by ID."""
    with next(get_session()) as session:
        record = session.get(WildcardRecord, wildcard_id)
        if not record:
            raise HTTPException(status_code=404, detail="Wildcard not found")
        return WildcardRecordSchema.from_orm(record)


@router.delete("/{wildcard_id}")
async def delete_wildcard(wildcard_id: int):
    """Delete a wildcard record."""
    with next(get_session()) as session:
        record = session.get(WildcardRecord, wildcard_id)
        if not record:
            raise HTTPException(status_code=404, detail="Wildcard not found")

        session.delete(record)
        session.commit()
        return {"status": "success", "message": "Wildcard deleted"}
