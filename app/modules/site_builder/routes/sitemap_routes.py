"""Sitemap routes — AI sitemap generation and section management."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.site_builder.services.sitemap_service import sitemap_service
from common_lib.modules.site_builder.services.project_service import project_service

router = APIRouter()


class SectionUpdateRequest(BaseModel):
    intent: Optional[str] = None
    description: Optional[str] = None
    block_id: Optional[str] = None
    variation_id: Optional[str] = None


class PageCreateRequest(BaseModel):
    title: str
    slug: str
    description: Optional[str] = None


class ReorderRequest(BaseModel):
    section_ids: list[str]


class SitemapResponse(BaseModel):
    success: bool
    data: dict
    message: str


class PageResponse(BaseModel):
    success: bool
    data: dict
    message: str


class SuccessResponse(BaseModel):
    success: bool
    data: dict
    message: str


@router.post("/projects/{project_id}/sitemap/generate", response_model=SitemapResponse)
def generate_sitemap(project_id: str, session: Session = Depends(get_db_session)):
    project = project_service.get(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update status to generating
    project_service.update(session, project_id, status="generating")

    # Use template-based generation (LLM integration available via orchestrator)
    from common_lib.modules.site_builder.orchestrator.nodes.sitemap_generator import (
        _generate_with_template,
    )

    pages_data = _generate_with_template(project.brief, project.page_count)

    # Persist generated sitemap
    sitemap_service.create_from_generation(session, project_id, pages_data)

    # Update status to ready
    project_service.update(session, project_id, status="ready")

    return SitemapResponse(
        success=True,
        data=sitemap_service.get_sitemap(session, project_id),
        message=f"Sitemap generated with {len(pages_data)} pages",
    )


@router.get("/projects/{project_id}/sitemap", response_model=SitemapResponse)
def get_sitemap(project_id: str, session: Session = Depends(get_db_session)):
    data = sitemap_service.get_sitemap(session, project_id)
    if not data:
        raise HTTPException(status_code=404, detail="Project not found")
    return SitemapResponse(success=True, data=data, message="Sitemap retrieved")


@router.put(
    "/projects/{project_id}/sitemap/sections/{section_id}",
    response_model=SitemapResponse,
)
def update_section(
    project_id: str,
    section_id: str,
    req: SectionUpdateRequest,
    session: Session = Depends(get_db_session),
):
    section = sitemap_service.update_section(
        session,
        section_id,
        intent=req.intent,
        description=req.description,
        block_id=req.block_id,
        variation_id=req.variation_id,
    )
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return SitemapResponse(
        success=True,
        data=sitemap_service.get_sitemap(session, project_id),
        message="Section updated",
    )


@router.post("/projects/{project_id}/sitemap/pages", response_model=PageResponse)
def add_page(
    project_id: str, req: PageCreateRequest, session: Session = Depends(get_db_session)
):
    page = sitemap_service.add_page(
        session, project_id, title=req.title, slug=req.slug, description=req.description
    )
    if not page:
        raise HTTPException(status_code=404, detail="Project not found")
    return PageResponse(
        success=True,
        data={"id": page.id, "title": page.title, "slug": page.slug},
        message="Page added",
    )


@router.delete(
    "/projects/{project_id}/sitemap/pages/{page_id}", response_model=SuccessResponse
)
def remove_page(
    project_id: str, page_id: str, session: Session = Depends(get_db_session)
):
    deleted = sitemap_service.remove_page(session, page_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Page not found")
    return SuccessResponse(success=True, data={}, message="Page removed")


@router.put(
    "/projects/{project_id}/sitemap/pages/{page_id}/reorder",
    response_model=SuccessResponse,
)
def reorder_sections(
    project_id: str,
    page_id: str,
    req: ReorderRequest,
    session: Session = Depends(get_db_session),
):
    sitemap_service.reorder_sections(session, page_id, req.section_ids)
    return SuccessResponse(success=True, data={}, message="Sections reordered")
