"""Custom Data REST Routes — Domain 13."""
import logging
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.custom_data.service import CustomDataService
from common_lib.modules.project_management.schemas import (
    CustomObjectCreate, CustomObjectUpdate,
    ObjectFieldDefCreate, ObjectFieldDefUpdate,
    CustomObjectRecordCreate, CustomObjectRecordUpdate,
    CustomRelationshipCreate, FormulaFieldCreate, FormulaFieldUpdate,
    CalculatedFieldCreate, CalculatedFieldUpdate, LinkRecordsCreate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Custom Objects ---
@router.post("/custom-objects", tags=["PM Custom Data"])
async def create_custom_object(data: CustomObjectCreate, _perm: None = require_permission("custom_data.create", "*", "custom_data")):
    return CustomDataService.create_custom_object(data)


@router.get("/custom-objects/{project_id}", tags=["PM Custom Data"])
async def list_custom_objects(project_id: str, include_inactive: bool = Query(False), _perm: None = require_permission("custom_data.read", "*", "custom_data")):
    return CustomDataService.list_custom_objects(project_id, include_inactive=include_inactive)


@router.get("/custom-objects/detail/{object_id}", tags=["PM Custom Data"])
async def get_custom_object(object_id: str, _perm: None = require_permission("custom_data.read", "*", "custom_data")):
    obj = CustomDataService.get_custom_object(object_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Custom object not found")
    return obj


@router.patch("/custom-objects/{object_id}", tags=["PM Custom Data"])
async def update_custom_object(object_id: str, data: CustomObjectUpdate, _perm: None = require_permission("custom_data.update", "*", "custom_data")):
    obj = CustomDataService.update_custom_object(object_id, data)
    if not obj:
        raise HTTPException(status_code=404, detail="Custom object not found")
    return obj


@router.delete("/custom-objects/{object_id}", tags=["PM Custom Data"])
async def delete_custom_object(object_id: str, _perm: None = require_permission("custom_data.delete", "*", "custom_data")):
    if not CustomDataService.delete_custom_object(object_id):
        raise HTTPException(status_code=404, detail="Custom object not found")
    return {"ok": True}


# --- Object Fields ---
@router.get("/custom-objects/{object_id}/fields", tags=["PM Custom Data"])
async def list_fields(object_id: str, _perm: None = require_permission("custom_data.read", "*", "custom_data")):
    return CustomDataService.list_fields(object_id)


@router.post("/custom-objects/{object_id}/fields", tags=["PM Custom Data"])
async def create_field(object_id: str, data: ObjectFieldDefCreate, _perm: None = require_permission("custom_data.create", "*", "custom_data")):
    return CustomDataService.create_field(data, object_id)


@router.patch("/custom-objects/{object_id}/fields/{field_id}", tags=["PM Custom Data"])
async def update_field(object_id: str, field_id: str, data: ObjectFieldDefUpdate, _perm: None = require_permission("custom_data.update", "*", "custom_data")):
    fd = CustomDataService.update_field(field_id, data)
    if not fd:
        raise HTTPException(status_code=404, detail="Field not found")
    return fd


@router.delete("/custom-objects/{object_id}/fields/{field_id}", tags=["PM Custom Data"])
async def delete_field(object_id: str, field_id: str, _perm: None = require_permission("custom_data.delete", "*", "custom_data")):
    if not CustomDataService.delete_field(field_id):
        raise HTTPException(status_code=404, detail="Field not found")
    return {"ok": True}


# --- Records ---
@router.post("/custom-objects/{object_id}/records", tags=["PM Custom Data"])
async def create_record(object_id: str, data: CustomObjectRecordCreate, _perm: None = require_permission("custom_data.create", "*", "custom_data")):
    result = CustomDataService.create_record(object_id, data)
    if "validation_errors" in result and result["validation_errors"]:
        return HTTPException(status_code=422, detail=result)
    return result


@router.get("/custom-objects/{object_id}/records", tags=["PM Custom Data"])
async def list_records(
    object_id: str,
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("custom_data.read", "*", "custom_data"),
):
    records, total = CustomDataService.list_records(object_id, search=search, limit=limit, offset=offset)
    return {"records": records, "total": total, "has_more": offset + limit < total}


@router.get("/custom-objects/{object_id}/records/{record_id}", tags=["PM Custom Data"])
async def get_record(object_id: str, record_id: str, _perm: None = require_permission("custom_data.read", "*", "custom_data")):
    record = CustomDataService.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.patch("/custom-objects/{object_id}/records/{record_id}", tags=["PM Custom Data"])
async def update_record(object_id: str, record_id: str, data: CustomObjectRecordUpdate, _perm: None = require_permission("custom_data.update", "*", "custom_data")):
    result = CustomDataService.update_record(record_id, data)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    if "validation_errors" in result and result["validation_errors"]:
        raise HTTPException(status_code=422, detail=result)
    return result["record"]


@router.delete("/custom-objects/{object_id}/records/{record_id}", tags=["PM Custom Data"])
async def delete_record(object_id: str, record_id: str, _perm: None = require_permission("custom_data.delete", "*", "custom_data")):
    if not CustomDataService.delete_record(record_id):
        raise HTTPException(status_code=404, detail="Record not found")
    return {"ok": True}


# --- Custom Relationships ---
@router.post("/relationships", tags=["PM Custom Data"])
async def create_relationship(data: CustomRelationshipCreate, _perm: None = require_permission("custom_data.create", "*", "custom_data")):
    return CustomDataService.create_relationship(data)


@router.get("/relationships/{project_id}", tags=["PM Custom Data"])
async def list_relationships(project_id: str, _perm: None = require_permission("custom_data.read", "*", "custom_data")):
    return CustomDataService.list_relationships(project_id)


@router.post("/relationships/link", tags=["PM Custom Data"])
async def link_records(data: LinkRecordsCreate, _perm: None = require_permission("custom_data.create", "*", "custom_data")):
    return CustomDataService.link_records(data.relationship_id, data.source_record_id, data.target_record_id)


@router.delete("/relationships/unlink/{link_id}", tags=["PM Custom Data"])
async def unlink_records(link_id: str, _perm: None = require_permission("custom_data.delete", "*", "custom_data")):
    if not CustomDataService.unlink_records(link_id):
        raise HTTPException(status_code=404, detail="Link not found")
    return {"ok": True}


@router.get("/relationships/links/{record_id}", tags=["PM Custom Data"])
async def get_linked_records(record_id: str, relationship_id: Optional[str] = Query(None), _perm: None = require_permission("custom_data.read", "*", "custom_data")):
    return CustomDataService.get_linked_records(record_id, relationship_id=relationship_id)


# --- Formula Fields ---
@router.post("/formula-fields", tags=["PM Custom Data"])
async def create_formula_field(data: FormulaFieldCreate, _perm: None = require_permission("custom_data.create", "*", "custom_data")):
    return CustomDataService.create_formula_field(data)


@router.get("/formula-fields/{project_id}", tags=["PM Custom Data"])
async def list_formula_fields(project_id: str, entity_type: Optional[str] = Query(None), _perm: None = require_permission("custom_data.read", "*", "custom_data")):
    return CustomDataService.list_formula_fields(project_id, entity_type=entity_type)


@router.patch("/formula-fields/{field_id}", tags=["PM Custom Data"])
async def update_formula_field(field_id: str, data: FormulaFieldUpdate, _perm: None = require_permission("custom_data.update", "*", "custom_data")):
    ff = CustomDataService.update_formula_field(field_id, data)
    if not ff:
        raise HTTPException(status_code=404, detail="Formula field not found")
    return ff


@router.get("/formula-fields/{field_id}/evaluate/{record_id}", tags=["PM Custom Data"])
async def evaluate_formula(field_id: str, record_id: str, _perm: None = require_permission("custom_data.read", "*", "custom_data")):
    return {"result": CustomDataService.evaluate_formula(field_id, record_id)}


# --- Calculated Fields ---
@router.post("/calculated-fields", tags=["PM Custom Data"])
async def create_calculated_field(data: CalculatedFieldCreate, _perm: None = require_permission("custom_data.create", "*", "custom_data")):
    return CustomDataService.create_calculated_field(data)


@router.get("/calculated-fields/{project_id}", tags=["PM Custom Data"])
async def list_calculated_fields(project_id: str, _perm: None = require_permission("custom_data.read", "*", "custom_data")):
    return CustomDataService.list_calculated_fields(project_id)


@router.patch("/calculated-fields/{field_id}", tags=["PM Custom Data"])
async def update_calculated_field(field_id: str, data: CalculatedFieldUpdate, _perm: None = require_permission("custom_data.update", "*", "custom_data")):
    cf = CustomDataService.update_calculated_field(field_id, data)
    if not cf:
        raise HTTPException(status_code=404, detail="Calculated field not found")
    return cf


@router.get("/calculated-fields/{field_id}/compute/{entity_id}", tags=["PM Custom Data"])
async def compute_calculated_field(field_id: str, entity_id: str, _perm: None = require_permission("custom_data.read", "*", "custom_data")):
    return {"result": CustomDataService.compute_calculated_field(field_id, entity_id)}


# --- Validation ---
@router.post("/validate-custom-fields/{project_id}", tags=["PM Custom Data"])
async def validate_custom_fields(project_id: str, data: dict, _perm: None = require_permission("custom_data.read", "*", "custom_data")):
    custom_fields = data.get("custom_fields", {})
    return CustomDataService.validate_custom_fields(project_id, custom_fields)
