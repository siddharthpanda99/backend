"""Forms, Intake & Work Routing REST routes — Domain 12."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.forms.service import FormService
from common_lib.modules.project_management.schemas import (
    FormCreate, FormUpdate, FormFieldCreate, FormFieldUpdate,
    FormSubmissionCreate, IntakeMappingCreate, IntakeMappingUpdate,
)

router = APIRouter(prefix="/forms", tags=["PM Forms"])


# ── Form CRUD ─────────────────────────────────────────────────────────

@router.post("")
def create_form(data: FormCreate, _perm: None = require_permission("form.create", "*", "form")):
    return FormService.create_form(data)


@router.get("")
def list_forms(
    project_id: Optional[str] = Query(None),
    form_type: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("form.read", "*", "form"),
):
    items, total = FormService.list_forms(project_id, form_type, include_inactive, limit, offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{form_id}")
def get_form(form_id: str, _perm: None = require_permission("form.read", "*", "form")):
    form = FormService.get_form(form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    return form


@router.patch("/{form_id}")
def update_form(form_id: str, data: FormUpdate, _perm: None = require_permission("form.update", "*", "form")):
    form = FormService.update_form(form_id, data)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    return form


@router.delete("/{form_id}")
def delete_form(form_id: str, _perm: None = require_permission("form.delete", "*", "form")):
    if not FormService.delete_form(form_id):
        raise HTTPException(status_code=404, detail="Form not found")
    return {"ok": True}


# ── Form Fields ───────────────────────────────────────────────────────

@router.get("/{form_id}/fields")
def list_fields(form_id: str, _perm: None = require_permission("form.read", "*", "form")):
    return FormService.list_fields(form_id)


@router.post("/{form_id}/fields")
def create_field(form_id: str, data: FormFieldCreate, _perm: None = require_permission("form.update", "*", "form")):
    field = FormService.create_field(form_id, data)
    if not field:
        raise HTTPException(status_code=404, detail="Form not found")
    return field


@router.patch("/{form_id}/fields/{field_id}")
def update_field(form_id: str, field_id: str, data: FormFieldUpdate, _perm: None = require_permission("form.update", "*", "form")):
    field = FormService.update_field(field_id, data)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    return field


@router.delete("/{form_id}/fields/{field_id}")
def delete_field(form_id: str, field_id: str, _perm: None = require_permission("form.update", "*", "form")):
    if not FormService.delete_field(field_id):
        raise HTTPException(status_code=404, detail="Field not found")
    return {"ok": True}


# ── Form Submissions ──────────────────────────────────────────────────

@router.post("/{form_id}/submit")
def submit_form(form_id: str, data: FormSubmissionCreate, _perm: None = require_permission("form.submit", "*", "form")):
    result = FormService.submit_form(form_id, data)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    if result.get("validation_errors"):
        raise HTTPException(status_code=422, detail=result["validation_errors"])
    return result


@router.get("/{form_id}/submissions")
def list_submissions(
    form_id: str,
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("form.read", "*", "form"),
):
    items, total = FormService.list_submissions(form_id, status, limit, offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/submissions/{submission_id}")
def get_submission(submission_id: str, _perm: None = require_permission("form.read", "*", "form")):
    sub = FormService.get_submission(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return sub


@router.patch("/submissions/{submission_id}/status")
def update_submission_status(
    submission_id: str,
    status: str = Query(...),
    mapped_issue_id: Optional[str] = Query(None),
    _perm: None = require_permission("form.update", "*", "form"),
):
    sub = FormService.update_submission_status(submission_id, status, mapped_issue_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return sub


@router.delete("/submissions/{submission_id}")
def delete_submission(submission_id: str, _perm: None = require_permission("form.update", "*", "form")):
    if not FormService.delete_submission(submission_id):
        raise HTTPException(status_code=404, detail="Submission not found")
    return {"ok": True}


# ── Intake Mappings ──────────────────────────────────────────────────

@router.post("/{form_id}/mappings")
def create_intake_mapping(form_id: str, data: IntakeMappingCreate, _perm: None = require_permission("form.update", "*", "form")):
    # Pass form_id in the model - Pydantic v2 allows setting after construction
    create_data = data.model_dump()
    create_data["form_id"] = form_id
    return FormService.create_intake_mapping(IntakeMappingCreate(**create_data))


@router.get("/{form_id}/mappings")
def list_intake_mappings(form_id: str, _perm: None = require_permission("form.read", "*", "form")):
    return FormService.list_intake_mappings(form_id)


@router.patch("/mappings/{mapping_id}")
def update_intake_mapping(mapping_id: str, data: IntakeMappingUpdate, _perm: None = require_permission("form.update", "*", "form")):
    mapping = FormService.update_intake_mapping(mapping_id, data)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return mapping


@router.delete("/mappings/{mapping_id}")
def delete_intake_mapping(mapping_id: str, _perm: None = require_permission("form.update", "*", "form")):
    if not FormService.delete_intake_mapping(mapping_id):
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"ok": True}
