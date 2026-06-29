"""Wireframe routes — block swapping, variation shuffling, content editing."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.site_builder.services.wireframe_service import wireframe_service

router = APIRouter()


class BlockSwapRequest(BaseModel):
    block_id: str


class ContentUpdateRequest(BaseModel):
    content_json: dict


class WireframeResponse(BaseModel):
    success: bool
    data: dict
    message: str


class SectionResponse(BaseModel):
    success: bool
    data: dict
    message: str


def _section_to_dict(s) -> dict:
    return {
        "id": s.id,
        "page_id": s.page_id,
        "intent": s.intent,
        "description": s.description,
        "block_id": s.block_id,
        "variation_id": s.variation_id,
        "order_index": s.order_index,
        "content_json": s.content_json,
        "seo_json": s.seo_json,
    }


@router.get("/projects/{project_id}/wireframe", response_model=WireframeResponse)
def get_wireframe(project_id: str, session: Session = Depends(get_db_session)):
    data = wireframe_service.get_wireframe(session, project_id)
    if not data.get("pages"):
        raise HTTPException(status_code=404, detail="Project not found or has no pages")
    return WireframeResponse(success=True, data=data, message="Wireframe retrieved")


@router.put(
    "/projects/{project_id}/wireframe/sections/{section_id}/block",
    response_model=SectionResponse,
)
def swap_block(
    project_id: str,
    section_id: str,
    req: BlockSwapRequest,
    session: Session = Depends(get_db_session),
):
    section = wireframe_service.swap_block(session, section_id, req.block_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section or block not found")
    return SectionResponse(
        success=True, data=_section_to_dict(section), message="Block swapped"
    )


@router.post(
    "/projects/{project_id}/wireframe/sections/{section_id}/shuffle",
    response_model=SectionResponse,
)
def shuffle_variation(
    project_id: str, section_id: str, session: Session = Depends(get_db_session)
):
    section = wireframe_service.shuffle_variation(session, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found or has no block")
    return SectionResponse(
        success=True, data=_section_to_dict(section), message="Variation shuffled"
    )


@router.put(
    "/projects/{project_id}/wireframe/sections/{section_id}/content",
    response_model=SectionResponse,
)
def update_content(
    project_id: str,
    section_id: str,
    req: ContentUpdateRequest,
    session: Session = Depends(get_db_session),
):
    section = wireframe_service.update_content(session, section_id, req.content_json)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return SectionResponse(
        success=True, data=_section_to_dict(section), message="Content updated"
    )
