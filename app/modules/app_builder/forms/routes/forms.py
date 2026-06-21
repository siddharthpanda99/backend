"""
Form Builder — CRUD Routes for Form Definitions

Endpoints:
  GET    /                    — List all forms (search, pagination)
  GET    /{id}                — Get single form by ID
  POST   /                    — Create a new form definition
  PUT    /{id}                — Update an existing form definition
  DELETE /{id}                — Delete a form definition
  POST   /{id}/duplicate      — Duplicate a form definition (copy with new ID)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.forms.schemas import (
    FormDefinitionCreate,
    FormDefinitionUpdate,
    FormDefinitionResponse,
    FormDefinitionListResponse,
    APIResponse,
)
from common_lib.modules.app_builder.forms.service import FormService

logger = logging.getLogger(__name__)
router = APIRouter()
service = FormService()


@router.get("/", response_model=FormDefinitionListResponse)
async def list_forms(
    search: Optional[str] = Query(None, max_length=256),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    """
    List all form definitions with optional search by name.
    Supports pagination via offset/limit.
    """
    items, total = service.list_forms(db, search=search, offset=offset, limit=limit)
    return FormDefinitionListResponse(items=items, total=total)


@router.get("/{id}", response_model=FormDefinitionResponse)
async def get_form(id: str, db: Session = Depends(get_session)):
    """
    Get a single form definition by its ID.
    Raises 404 if not found.
    """
    record = service.get_form(db, id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Form '{id}' not found")
    return record


@router.post("/", response_model=FormDefinitionResponse, status_code=201)
async def create_form(data: FormDefinitionCreate, db: Session = Depends(get_session)):
    """
    Create a new form definition.
    """
    record = service.create_form(db, data)
    logger.info("Created form definition: %s (%s)", record.name, record.id)
    return record


@router.put("/{id}", response_model=FormDefinitionResponse)
async def update_form(id: str, data: FormDefinitionUpdate, db: Session = Depends(get_session)):
    """
    Update an existing form definition.
    """
    record = service.update_form(db, id, data)
    if not record:
        raise HTTPException(status_code=404, detail=f"Form '{id}' not found")
    logger.info("Updated form definition: %s (%s)", record.name, record.id)
    return record


@router.delete("/{id}", response_model=APIResponse)
async def delete_form(id: str, db: Session = Depends(get_session)):
    """
    Delete a form definition by its ID.
    """
    record = service.delete_form(db, id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Form '{id}' not found")
    logger.info("Deleted form definition: %s (%s)", record.name, id)
    return APIResponse(success=True, data={"id": id}, message=f"Form '{record.name}' deleted")


@router.post("/{id}/duplicate", response_model=FormDefinitionResponse, status_code=201)
async def duplicate_form(id: str, db: Session = Depends(get_session)):
    """
    Duplicate an existing form definition.
    """
    record = service.duplicate_form(db, id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Form '{id}' not found")
    logger.info("Duplicated form: %s -> %s (%s)", id, record.id, record.name)
    return record
