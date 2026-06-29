"""Registry routes — browse and search section block definitions."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.site_builder.services.registry_service import (
    component_registry_service,
)

router = APIRouter()


class RegistryResponse(BaseModel):
    success: bool
    data: list
    message: str


class BlockResponse(BaseModel):
    success: bool
    data: dict
    message: str


def _block_to_dict(b) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "category": b.category,
        "description": b.description,
        "layout": b.layout,
        "intent_tags": b.intent_tags,
        "variations_json": b.variations_json,
        "content_fields": b.content_fields,
        "thumbnail_url": b.thumbnail_url,
        "is_global": b.is_global,
    }


@router.get("/registry", response_model=RegistryResponse)
def list_blocks(
    category: Optional[str] = None, session: Session = Depends(get_db_session)
):
    blocks = component_registry_service.list_blocks(session, category=category)
    return RegistryResponse(
        success=True,
        data=[_block_to_dict(b) for b in blocks],
        message=f"Found {len(blocks)} blocks",
    )


@router.get("/registry/search", response_model=RegistryResponse)
def search_blocks(
    intent: str, top_k: int = 5, session: Session = Depends(get_db_session)
):
    blocks = component_registry_service.search_blocks(session, intent, top_k=top_k)
    return RegistryResponse(
        success=True,
        data=[_block_to_dict(b) for b in blocks],
        message=f"Found {len(blocks)} blocks for intent '{intent}'",
    )


@router.get("/registry/{block_id}", response_model=BlockResponse)
def get_block(block_id: str, session: Session = Depends(get_db_session)):
    block = component_registry_service.get_block(session, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return BlockResponse(
        success=True, data=_block_to_dict(block), message="Block retrieved"
    )
