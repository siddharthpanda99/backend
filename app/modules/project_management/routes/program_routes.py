"""Programs, Project Health & Dependencies REST Routes — Domain 02 gaps."""
import logging
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.programs.service import ProgramService
from common_lib.modules.project_management.schemas import (
    ProgramCreate, ProgramUpdate, ProjectDependencyCreate, ProjectRiskFlagCreate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Programs ---
@router.post("/programs", tags=["PM Programs"])
async def create_program(data: ProgramCreate, _perm: None = require_permission("project.create", "*", "project")):
    return ProgramService.create_program(data)


@router.get("/programs/{program_id}", tags=["PM Programs"])
async def get_program(program_id: str, _perm: None = require_permission("project.read", "*", "project")):
    program = ProgramService.get_program(program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    return program


@router.get("/programs", tags=["PM Programs"])
async def list_programs(_perm: None = require_permission("project.read", "*", "project"),
    organization_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return ProgramService.list_programs(organization_id=organization_id, status=status, limit=limit, offset=offset)


@router.patch("/programs/{program_id}", tags=["PM Programs"])
async def update_program(program_id: str, data: ProgramUpdate, _perm: None = require_permission("project.update", "*", "project")):
    program = ProgramService.update_program(program_id, data)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    return program


@router.delete("/programs/{program_id}", tags=["PM Programs"])
async def delete_program(program_id: str, _perm: None = require_permission("project.delete", "*", "project")):
    if not ProgramService.delete_program(program_id):
        raise HTTPException(status_code=404, detail="Program not found")
    return {"ok": True}


# --- Hierarchy Trees ---
@router.get("/programs/tree", tags=["PM Programs"])
async def get_program_tree(organization_id: Optional[str] = None, _perm: None = require_permission("project.read", "*", "project")):
    return ProgramService.get_program_tree(organization_id=organization_id)


@router.get("/portfolios/tree", tags=["PM Programs"])
async def get_portfolio_tree(organization_id: Optional[str] = None, _perm: None = require_permission("project.read", "*", "project")):
    return ProgramService.get_portfolio_tree(organization_id=organization_id)


# --- Project Dependencies ---
@router.post("/project-dependencies", tags=["PM Programs"])
async def create_project_dependency(data: ProjectDependencyCreate, _perm: None = require_permission("project.update", "*", "project")):
    return ProgramService.create_project_dependency(data)


@router.get("/project-dependencies", tags=["PM Programs"])
async def list_project_dependencies(_perm: None = require_permission("project.read", "*", "project"),
    project_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return ProgramService.list_project_dependencies(project_id=project_id, limit=limit, offset=offset)


@router.delete("/project-dependencies/{dep_id}", tags=["PM Programs"])
async def delete_project_dependency(dep_id: str, _perm: None = require_permission("project.delete", "*", "project")):
    if not ProgramService.delete_project_dependency(dep_id):
        raise HTTPException(status_code=404, detail="Dependency not found")
    return {"ok": True}


# --- Project Health ---
@router.get("/health/compute/{project_id}", tags=["PM Programs"])
async def compute_project_health(project_id: str, _perm: None = require_permission("project.read", "*", "project")):
    return ProgramService.compute_project_health(project_id)


@router.get("/health/history/{project_id}", tags=["PM Programs"])
async def get_health_history(project_id: str, limit: int = Query(30, ge=1, le=365), _perm: None = require_permission("project.read", "*", "project")):
    return ProgramService.get_health_history(project_id, limit=limit)


# --- Risk Flags ---
@router.post("/risk-flags", tags=["PM Programs"])
async def create_risk_flag(data: ProjectRiskFlagCreate, _perm: None = require_permission("project.update", "*", "project")):
    return ProgramService.create_risk_flag(data)


@router.get("/risk-flags/{project_id}", tags=["PM Programs"])
async def list_risk_flags(project_id: str, status: Optional[str] = None, _perm: None = require_permission("project.read", "*", "project")):
    return ProgramService.list_risk_flags(project_id, status=status)


@router.post("/risk-flags/{flag_id}/resolve", tags=["PM Programs"])
async def resolve_risk_flag(flag_id: str, _perm: None = require_permission("project.update", "*", "project")):
    flag = ProgramService.resolve_risk_flag(flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Risk flag not found")
    return flag


# --- Multi-Project Dashboard ---
@router.get("/multi-project-dashboard", tags=["PM Programs"])
async def get_multi_project_dashboard(_perm: None = require_permission("project.read", "*", "project"),
    program_id: Optional[str] = Query(None),
    project_ids: Optional[str] = Query(None),
):
    pids = project_ids.split(",") if project_ids else None
    return ProgramService.get_multi_project_dashboard(program_id=program_id, project_ids=pids)
