from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.modules.database.service.connection import get_session
from app.modules.projects.schemas.project import ProjectRead, ProjectCreate, ProjectUpdate
from app.modules.projects.service.project_service import ProjectService

router = APIRouter()

@router.get("/", response_model=List[ProjectRead])
def read_projects(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session)
):
    service = ProjectService(session)
    return service.list_projects(skip=skip, limit=limit)

@router.get("/{project_id}", response_model=ProjectRead)
def read_project(
    project_id: int,
    session: Session = Depends(get_session)
):
    service = ProjectService(session)
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.post("/", response_model=ProjectRead)
def create_project(
    project_in: ProjectCreate,
    session: Session = Depends(get_session)
):
    service = ProjectService(session)
    # TODO: Get current user ID from auth context
    return service.create_project(project_in)

@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    project_in: ProjectUpdate,
    session: Session = Depends(get_session)
):
    service = ProjectService(session)
    project = service.update_project(project_id, project_in)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    session: Session = Depends(get_session)
):
    service = ProjectService(session)
    if not service.delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}
