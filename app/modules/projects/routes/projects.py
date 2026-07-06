from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.projects.schemas import (
    ProjectRead,
    ProjectCreate,
    ProjectUpdate,
)
from common_lib.modules.projects.service import ProjectService
from common_lib.modules.auth.authorization import PlatformIdentity, log_crud_mutation
from app.modules.auth.dependencies import require_permission, require_tenant

router = APIRouter()


def get_project_service(session: Session = Depends(get_session)) -> ProjectService:
    return ProjectService(session)


@router.get(
    "/",
    response_model=List[ProjectRead],
    dependencies=[
        Depends(require_tenant),
        require_permission("project.read", "*", "project"),
    ],
)
def read_projects(
    skip: int = 0,
    limit: int = 100,
    service: ProjectService = Depends(get_project_service),
):
    return service.list_projects(skip=skip, limit=limit)


@router.get(
    "/{project_id}",
    response_model=ProjectRead,
    dependencies=[
        Depends(require_tenant),
        require_permission("project.read", "*", "project"),
    ],
)
def read_project(
    project_id: int, service: ProjectService = Depends(get_project_service)
):
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post(
    "/",
    response_model=ProjectRead,
    dependencies=[
        Depends(require_tenant),
        require_permission("project.create", "*", "project"),
    ],
)
def create_project(
    request: Request,
    project_in: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
):
    # Pass along to the existing project service
    result = service.create_project(project_in)
    
    # Provision the database if requested
    if project_in.database_type:
        from common_lib.modules.db_provisioning.service import db_provisioner
        try:
            db_url = db_provisioner.provision_db(result.slug, project_in.database_type)
            # We would update the project record here with the db_url
            if db_url:
                result = service.update_project(result.id, ProjectUpdate(database_url=db_url))
        except Exception as e:
            # We log it, but still return the created project
            import logging
            logging.getLogger(__name__).error(f"Failed to provision {project_in.database_type} for project {result.id}: {e}")

    ident: PlatformIdentity = request.state.identity
    log_crud_mutation(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="project.create",
        resource_id=str(result.id),
        resource_type="project",
        tenant_id=ident.tenant_id,
    )
    return result


@router.patch(
    "/{project_id}",
    response_model=ProjectRead,
    dependencies=[
        Depends(require_tenant),
        require_permission("project.update", "*", "project"),
    ],
)
def update_project(
    request: Request,
    project_id: int,
    project_in: ProjectUpdate,
    service: ProjectService = Depends(get_project_service),
):
    project = service.update_project(project_id, project_in)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    ident: PlatformIdentity = request.state.identity
    log_crud_mutation(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="project.update",
        resource_id=str(project_id),
        resource_type="project",
        tenant_id=ident.tenant_id,
    )
    return project


@router.delete(
    "/{project_id}",
    dependencies=[
        Depends(require_tenant),
        require_permission("project.delete", "*", "project"),
    ],
)
def delete_project(
    request: Request,
    project_id: int,
    service: ProjectService = Depends(get_project_service),
):
    if not service.delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    ident: PlatformIdentity = request.state.identity
    log_crud_mutation(
        subject_id=ident.subject_id,
        subject_type=ident.subject_type,
        action="project.delete",
        resource_id=str(project_id),
        resource_type="project",
        tenant_id=ident.tenant_id,
    )
    return {"ok": True}
