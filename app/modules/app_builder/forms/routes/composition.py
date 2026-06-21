"""
Form Builder — Composition & Sub-Form Resolution

Provides endpoints for working with composable forms that reference other
forms as sub-components via the `form_ref` field type.

Endpoints:
  GET    /{id}/compose          — Resolve form with all sub-form refs expanded
  GET    /{id}/compose/flat     — Flatten a composed form into a single field list
  GET    /{id}/references       — List all form_ref dependencies (what this form uses)
  GET    /{id}/referenced-by    — List all forms that reference this one
  POST   /{id}/validate-refs    — Validate all form_ref targets exist, detect cycles
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.forms.schemas import (
    APIResponse,
)
from common_lib.modules.app_builder.forms.service import FormService

logger = logging.getLogger(__name__)
router = APIRouter()
service = FormService()


@router.get("/{id}/compose", response_model=APIResponse)
async def compose_form(id: str, db: Session = Depends(get_session)):
    """
    Resolve a form definition with all sub-form references expanded.
    """
    composed = service.compose_form(db, id)
    if not composed:
        raise HTTPException(status_code=404, detail=f"Form '{id}' not found")
    return APIResponse(data=composed)


@router.get("/{id}/compose/flat", response_model=APIResponse)
async def compose_form_flat(id: str, db: Session = Depends(get_session)):
    """
    Resolve a composed form into a single flat list of fields.
    """
    flat = service.compose_form_flat(db, id)
    if not flat:
        raise HTTPException(status_code=404, detail=f"Form '{id}' not found")
    return APIResponse(data=flat)


@router.get("/{id}/references", response_model=APIResponse)
async def get_form_references(id: str, db: Session = Depends(get_session)):
    """
    List all forms that this form references via form_ref fields.
    """
    refs = service.get_form_references(db, id)
    if not refs:
        raise HTTPException(status_code=404, detail=f"Form '{id}' not found")
    return APIResponse(data=refs)


@router.get("/{id}/referenced-by", response_model=APIResponse)
async def get_form_referenced_by(id: str, db: Session = Depends(get_session)):
    """
    List all forms that reference this form as a sub-form.
    """
    ref_by = service.get_form_referenced_by(db, id)
    if not ref_by:
        raise HTTPException(status_code=404, detail=f"Form '{id}' not found")
    return APIResponse(data=ref_by)


@router.post("/{id}/validate-refs", response_model=APIResponse)
async def validate_form_refs(id: str, db: Session = Depends(get_session)):
    """
    Validate all form_ref targets within a form definition.
    """
    validation = service.validate_form_refs(db, id)
    if not validation:
        raise HTTPException(status_code=404, detail=f"Form '{id}' not found")
    return APIResponse(data=validation)
