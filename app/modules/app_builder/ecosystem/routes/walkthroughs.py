"""
App Ecosystem — Walkthrough CRUD Routes

/api/v1/ecosystem/apps/{app_id}/walkthroughs — list, create, update, delete, steps
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.ecosystem.schemas import (
    WalkthroughCreate, WalkthroughUpdate, WalkthroughSchema,
    PaginatedResponse, APIResponse,
)
from common_lib.modules.app_builder.ecosystem.service import EcosystemService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/apps/{app_id}/walkthroughs", tags=["Ecosystem — Walkthroughs"])
service = EcosystemService()


@router.get("/", response_model=PaginatedResponse)
async def list_walkthroughs(
    app_id: str,
    difficulty: Optional[str] = Query(None, pattern="^(beginner|intermediate|advanced)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    """List walkthroughs for an app."""
    try:
        records, total = service.list_walkthroughs(
            db, app_id, difficulty=difficulty, page=page, page_size=page_size
        )
        return PaginatedResponse(
            items=records,
            total=total,
            page=page,
            page_size=page_size,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{walkthrough_id}", response_model=WalkthroughSchema)
async def get_walkthrough(app_id: str, walkthrough_id: str, db: Session = Depends(get_session)):
    """Get a single walkthrough with its steps."""
    try:
        record = service.get_walkthrough(db, app_id, walkthrough_id)
        if not record:
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        return record
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/", response_model=APIResponse, status_code=201)
async def create_walkthrough(app_id: str, data: WalkthroughCreate, db: Session = Depends(get_session)):
    """Create a new walkthrough with steps for an app."""
    try:
        record = service.create_walkthrough(db, app_id, data)
        return APIResponse(
            status="success",
            message="Walkthrough created",
            data=record.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{walkthrough_id}", response_model=APIResponse)
async def update_walkthrough(
    app_id: str,
    walkthrough_id: str,
    data: WalkthroughUpdate,
    db: Session = Depends(get_session),
):
    """Update a walkthrough (replace steps if provided)."""
    try:
        record = service.update_walkthrough(db, app_id, walkthrough_id, data)
        if not record:
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        return APIResponse(
            status="success",
            message="Walkthrough updated",
            data=record.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{walkthrough_id}/complete", response_model=APIResponse)
async def complete_walkthrough(app_id: str, walkthrough_id: str, db: Session = Depends(get_session)):
    """Increment the completion counter for a walkthrough."""
    try:
        completions = service.complete_walkthrough(db, app_id, walkthrough_id)
        if completions is None:
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        return APIResponse(
            status="success",
            data={"completions": completions},
            message="Walkthrough completion recorded",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{walkthrough_id}", response_model=APIResponse)
async def delete_walkthrough(app_id: str, walkthrough_id: str, db: Session = Depends(get_session)):
    """Delete a walkthrough and its steps."""
    try:
        success = service.delete_walkthrough(db, app_id, walkthrough_id)
        if not success:
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        return APIResponse(status="success", message="Walkthrough deleted")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
