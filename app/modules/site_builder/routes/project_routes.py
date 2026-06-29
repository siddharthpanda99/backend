"""Project routes — CRUD for site projects."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.site_builder.services.project_service import project_service

router = APIRouter()


class ProjectCreateRequest(BaseModel):
    name: str
    brief: str
    page_count: int = 3
    language: str = "en"
    brand_voice: str = "professional"


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    brief: Optional[str] = None
    page_count: Optional[int] = None
    language: Optional[str] = None
    brand_voice: Optional[str] = None
    status: Optional[str] = None
    theme_id: Optional[str] = None


class ProjectResponse(BaseModel):
    success: bool
    data: dict
    message: str


class ProjectListResponse(BaseModel):
    success: bool
    data: list
    message: str


def _project_to_dict(p) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "brief": p.brief,
        "page_count": p.page_count,
        "language": p.language,
        "brand_voice": p.brand_voice,
        "status": p.status,
        "theme_id": p.theme_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.post("/", response_model=ProjectResponse)
def create_project(
    req: ProjectCreateRequest, session: Session = Depends(get_db_session)
):
    project = project_service.create(
        session,
        name=req.name,
        brief=req.brief,
        page_count=req.page_count,
        language=req.language,
        brand_voice=req.brand_voice,
    )
    return ProjectResponse(
        success=True, data=_project_to_dict(project), message="Project created"
    )


@router.get("/", response_model=ProjectListResponse)
def list_projects(
    status: Optional[str] = None, session: Session = Depends(get_db_session)
):
    projects = project_service.list(session, status=status)
    return ProjectListResponse(
        success=True,
        data=[_project_to_dict(p) for p in projects],
        message=f"Found {len(projects)} projects",
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, session: Session = Depends(get_db_session)):
    project = project_service.get(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        success=True, data=_project_to_dict(project), message="Project retrieved"
    )


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    req: ProjectUpdateRequest,
    session: Session = Depends(get_db_session),
):
    kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
    project = project_service.update(session, project_id, **kwargs)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        success=True, data=_project_to_dict(project), message="Project updated"
    )


@router.delete("/{project_id}", response_model=ProjectResponse)
def delete_project(project_id: str, session: Session = Depends(get_db_session)):
    deleted = project_service.delete(session, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(success=True, data={}, message="Project deleted")
