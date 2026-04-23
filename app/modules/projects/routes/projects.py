from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.projects.schemas import (
    ProjectRead,
    ProjectCreate,
    ProjectUpdate,
)
from common_lib.modules.projects.service import ProjectService

router = APIRouter()


def get_project_service(session: Session = Depends(get_session)) -> ProjectService:
    return ProjectService(session)


@router.get("/", response_model=List[ProjectRead])
def read_projects(
    skip: int = 0,
    limit: int = 100,
    service: ProjectService = Depends(get_project_service),
):
    return service.list_projects(skip=skip, limit=limit)


@router.get("/{project_id}", response_model=ProjectRead)
def read_project(
    project_id: int, service: ProjectService = Depends(get_project_service)
):
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/", response_model=ProjectRead)
def create_project(
    project_in: ProjectCreate, service: ProjectService = Depends(get_project_service)
):
    return service.create_project(project_in)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    project_in: ProjectUpdate,
    service: ProjectService = Depends(get_project_service),
):
    project = service.update_project(project_id, project_in)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
def delete_project(
    project_id: int, service: ProjectService = Depends(get_project_service)
):
    if not service.delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}
