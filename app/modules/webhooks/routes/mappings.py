"""
Webhook Manager — Event-Workflow Mapping Routes

/api/v1/webhooks/event-mappings — CRUD for event→workflow automations.
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, delete as sql_delete

from common_lib.modules.data_storage.database.connection import get_session
from ..models import EventWorkflowMappingRecord
from ..schemas import (
    EventWorkflowMappingCreate,
    EventWorkflowMappingUpdate,
    EventWorkflowMappingResponse,
    EventWorkflowMappingListResponse,
    APIResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/event-mappings", tags=["Event-Workflow Mappings"])


def _generate_mapping_id() -> str:
    return f"ewm_{uuid.uuid4().hex[:12]}"


@router.get("/", response_model=EventWorkflowMappingListResponse)
async def list_mappings(
    event_type: Optional[str] = Query(None),
    workflow_id: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    query = select(EventWorkflowMappingRecord).order_by(
        EventWorkflowMappingRecord.created_at.desc()
    )

    if event_type:
        query = query.where(EventWorkflowMappingRecord.event_type == event_type)
    if workflow_id:
        query = query.where(EventWorkflowMappingRecord.workflow_id == workflow_id)
    if enabled is not None:
        query = query.where(EventWorkflowMappingRecord.enabled == enabled)

    total = len(db.execute(query).scalars().all())
    items = db.execute(query.offset(offset).limit(limit)).scalars().all()

    return EventWorkflowMappingListResponse(
        items=[EventWorkflowMappingResponse.model_validate(m) for m in items],
        total=total,
    )


@router.get("/{mapping_id}", response_model=EventWorkflowMappingResponse)
async def get_mapping(
    mapping_id: str,
    db: Session = Depends(get_session),
):
    m = db.execute(
        select(EventWorkflowMappingRecord).where(
            EventWorkflowMappingRecord.id == mapping_id
        )
    ).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return EventWorkflowMappingResponse.model_validate(m)


@router.post("/", response_model=EventWorkflowMappingResponse, status_code=201)
async def create_mapping(
    data: EventWorkflowMappingCreate,
    db: Session = Depends(get_session),
):
    mapping = EventWorkflowMappingRecord(
        id=_generate_mapping_id(),
        event_type=data.event_type,
        workflow_id=data.workflow_id,
        workflow_inputs=data.workflow_inputs,
        enabled=data.enabled,
        description=data.description,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    logger.info(
        f"Created event mapping: '{data.event_type}' → '{data.workflow_id}' "
        f"(id={mapping.id})"
    )
    return EventWorkflowMappingResponse.model_validate(mapping)


@router.put("/{mapping_id}", response_model=EventWorkflowMappingResponse)
async def update_mapping(
    mapping_id: str,
    data: EventWorkflowMappingUpdate,
    db: Session = Depends(get_session),
):
    m = db.execute(
        select(EventWorkflowMappingRecord).where(
            EventWorkflowMappingRecord.id == mapping_id
        )
    ).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Mapping not found")

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(m, key, value)

    db.commit()
    db.refresh(m)
    return EventWorkflowMappingResponse.model_validate(m)


@router.delete("/{mapping_id}", response_model=APIResponse)
async def delete_mapping(
    mapping_id: str,
    db: Session = Depends(get_session),
):
    m = db.execute(
        select(EventWorkflowMappingRecord).where(
            EventWorkflowMappingRecord.id == mapping_id
        )
    ).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Mapping not found")

    db.delete(m)
    db.commit()
    logger.info(f"Deleted event mapping (id={mapping_id})")
    return APIResponse(success=True, message=f"Mapping '{mapping_id}' deleted")
