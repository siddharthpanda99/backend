"""Resource Management REST Routes — Domain 07."""
import logging
from datetime import date
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.schemas import (
    PeopleResourceCreate, PeopleResourceUpdate, SkillCreate,
    ResourceAllocationCreate, ResourceRequestCreate, LeaveRequestCreate,
)
from common_lib.modules.project_management.resources.service import ResourceService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/resources", tags=["PM Resources"])
async def create_resource(data: PeopleResourceCreate, _perm: None = require_permission("resource.create", "*", "resource")):
    try:
        return ResourceService.create_people_resource(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/resources/{resource_id}", tags=["PM Resources"])
async def get_resource(resource_id: str, _perm: None = require_permission("resource.read", "*", "resource")):
    resource = ResourceService.get_people_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


@router.get("/resources", tags=["PM Resources"])
async def list_resources(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    team_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    department: Optional[str] = None,
    _perm: None = require_permission("resource.read", "*", "resource"),
):
    return ResourceService.list_people_resources(limit=limit, offset=offset, team_id=team_id, is_active=is_active, department=department)


@router.patch("/resources/{resource_id}", tags=["PM Resources"])
async def update_resource(resource_id: str, data: PeopleResourceUpdate, _perm: None = require_permission("resource.update", "*", "resource")):
    resource = ResourceService.update_people_resource(resource_id, data)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


@router.delete("/resources/{resource_id}", tags=["PM Resources"])
async def delete_resource(resource_id: str, _perm: None = require_permission("resource.delete", "*", "resource")):
    if not ResourceService.delete_people_resource(resource_id):
        raise HTTPException(status_code=404, detail="Resource not found")
    return {"ok": True}


# --- Skills ---
@router.post("/skills", tags=["PM Resources"])
async def create_skill(data: SkillCreate, _perm: None = require_permission("skill.create", "*", "skill")):
    return ResourceService.create_skill(data)


@router.get("/skills", tags=["PM Resources"])
async def list_skills(
    category: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("skill.read", "*", "skill"),
):
    return ResourceService.list_skills(category=category, limit=limit, offset=offset)


# --- Allocations ---
@router.post("/allocations", tags=["PM Resources"])
async def create_allocation(data: ResourceAllocationCreate, _perm: None = require_permission("allocation.create", "*", "allocation")):
    return ResourceService.create_allocation(data)


@router.get("/allocations", tags=["PM Resources"])
async def list_allocations(
    resource_id: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("allocation.read", "*", "allocation"),
):
    return ResourceService.list_allocations(resource_id=resource_id, project_id=project_id, limit=limit, offset=offset)


@router.delete("/allocations/{allocation_id}", tags=["PM Resources"])
async def delete_allocation(allocation_id: str, _perm: None = require_permission("allocation.delete", "*", "allocation")):
    if not ResourceService.delete_allocation(allocation_id):
        raise HTTPException(status_code=404, detail="Allocation not found")
    return {"ok": True}


# --- Workload ---
@router.get("/workload", tags=["PM Resources"])
async def get_workload(
    date_from: str = Query(...),
    date_to: str = Query(...),
    team_id: Optional[str] = None,
    _perm: None = require_permission("workload.read", "*", "workload"),
):
    try:
        d_from = date.fromisoformat(date_from)
        d_to = date.fromisoformat(date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    return ResourceService.get_workload_view(d_from, d_to, team_id=team_id)


@router.get("/utilization", tags=["PM Resources"])
async def get_utilization(
    date_from: str = Query(...),
    date_to: str = Query(...),
    team_id: Optional[str] = None,
    _perm: None = require_permission("utilization.read", "*", "utilization"),
):
    try:
        d_from = date.fromisoformat(date_from)
        d_to = date.fromisoformat(date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    return ResourceService.get_utilization_report(d_from, d_to, team_id=team_id)


# --- Leave ---
@router.post("/leave-requests", tags=["PM Resources"])
async def create_leave_request(data: LeaveRequestCreate, _perm: None = require_permission("leave.create", "*", "leave")):
    return ResourceService.create_leave_request(data)


@router.get("/leave-requests", tags=["PM Resources"])
async def list_leave_requests(
    resource_id: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("leave.read", "*", "leave"),
):
    d_from = date.fromisoformat(date_from) if date_from else None
    d_to = date.fromisoformat(date_to) if date_to else None
    return ResourceService.list_leave_requests(resource_id=resource_id, status=status, date_from=d_from, date_to=d_to, limit=limit, offset=offset)


@router.post("/leave-requests/{leave_id}/approve", tags=["PM Resources"])
async def approve_leave_request(leave_id: str, approved_by: str = Query(...), _perm: None = require_permission("leave.update", "*", "leave")):
    result = ResourceService.approve_leave_request(leave_id, approved_by)
    if not result:
        raise HTTPException(status_code=404, detail="Leave request not found")
    return result


# --- Resource Requests ---
@router.post("/resource-requests", tags=["PM Resources"])
async def create_resource_request(data: ResourceRequestCreate, _perm: None = require_permission("resource_request.create", "*", "resource_request")):
    return ResourceService.create_resource_request(data)


@router.get("/resource-requests", tags=["PM Resources"])
async def list_resource_requests(
    status: Optional[str] = None,
    project_id: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("resource_request.read", "*", "resource_request"),
):
    return ResourceService.list_resource_requests(status=status, project_id=project_id, priority=priority, limit=limit, offset=offset)
