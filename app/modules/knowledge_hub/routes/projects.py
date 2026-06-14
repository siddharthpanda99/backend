"""
Knowledge Hub — Project Routes.

Endpoints:
    GET    /knowledge-hub/projects                — List projects
    POST   /knowledge-hub/projects                — Create project
    GET    /knowledge-hub/projects/{id}           — Get project
    PUT    /knowledge-hub/projects/{id}           — Update project
    DELETE /knowledge-hub/projects/{id}           — Delete project
    POST   /knowledge-hub/projects/{id}/verify    — Verify project
    POST   /knowledge-hub/projects/{id}/test-all  — Test all packets
    POST   /knowledge-hub/projects/{id}/attach    — Attach to agent
    POST   /knowledge-hub/projects/{id}/detach    — Detach from agent
    POST   /knowledge-hub/projects/{id}/build-data-object  — Build data object
    GET    /knowledge-hub/projects/{id}/data-object        — Get data object
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.knowledge_hub.models import (
    ActivityLogRecord,
    KnowledgeProjectRecord,
    ProjectMemberRecord,
)
from common_lib.modules.knowledge_hub.services.project_service import (
    ProjectService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-hub", tags=["Knowledge Hub — Projects"])


# ── Pydantic Schemas ───────────────────────────────────────────────


class ProjectCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., description="Project name")
    description: Optional[str] = None
    packet_ids: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    packet_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class AttachRequest(BaseModel):
    agent_id: str = Field(..., description="Agent ID to attach this project to")


class DuplicateRequest(BaseModel):
    include_docs: bool = Field(default=True, description="Whether to copy documents")


class AddMemberRequest(BaseModel):
    user_id: str = Field(..., description="User ID to add")
    role: str = Field(
        default="viewer",
        pattern="^(viewer|editor|admin)$",
        description="Role: viewer, editor, admin",
    )


class ChangeRoleRequest(BaseModel):
    role: str = Field(
        ...,
        pattern="^(viewer|editor|admin)$",
        description="New role: viewer, editor, admin",
    )


# ═══════════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("/projects")
def list_projects(
    status: Optional[str] = Query(None, description="Filter by status"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List knowledge projects."""
    projects = ProjectService.list_projects(session, status=status)
    return {
        "success": True,
        "data": [_project_to_dict(p) for p in projects],
        "total": len(projects),
    }


@router.get("/projects/{project_id}")
def get_project(
    project_id: str = Path(..., description="Project ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get a knowledge project by ID."""
    record = ProjectService.get_project(session, project_id)
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Project '{project_id}' not found"
        )
    return {"success": True, "data": _project_to_dict(record)}


@router.post("/projects", status_code=201)
def create_project(
    request: ProjectCreate,
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Create a new knowledge project."""
    record = ProjectService.create_project(session, request.model_dump())
    return {"success": True, "data": _project_to_dict(record)}


@router.put("/projects/{project_id}")
def update_project(
    request: ProjectUpdate,
    project_id: str = Path(..., description="Project ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Update an existing knowledge project."""
    record = ProjectService.update_project(
        session, project_id, request.model_dump(exclude_none=True)
    )
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Project '{project_id}' not found"
        )
    return {"success": True, "data": _project_to_dict(record)}


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: str = Path(..., description="Project ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Delete a knowledge project."""
    deleted = ProjectService.delete_project(session, project_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Project '{project_id}' not found"
        )
    return {"success": True, "message": f"Project '{project_id}' deleted"}


# ═══════════════════════════════════════════════════════════════════
# Test All / Verify / Attach / Detach / Data Object
# ═══════════════════════════════════════════════════════════════════


@router.post("/projects/{project_id}/test-all")
def test_all_project(
    project_id: str = Path(..., description="Project ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Test all packets in a project.

    Runs test-all on every associated packet, providing a consolidated
    status report of all sources and pipelines.
    """
    result = ProjectService.test_all(session, project_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=404, detail=f"Project '{project_id}' not found"
        )
    return result


@router.post("/projects/{project_id}/verify")
def verify_project(
    project_id: str = Path(..., description="Project ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Mark a project as verified.

    Only verified projects can be attached to agents. Runs all
    tests automatically before verifying. All sources and pipelines
    must pass for verification to succeed.
    """
    record = ProjectService.verify_project(session, project_id)
    if not record:
        existing = ProjectService.get_project(session, project_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot verify project '{project_id}': "
                    "run test-all first and ensure all packets pass"
                ),
            )
        raise HTTPException(
            status_code=404, detail=f"Project '{project_id}' not found"
        )
    return {
        "success": True,
        "data": _project_to_dict(record),
        "message": f"Project '{record.name}' verified successfully",
    }


@router.post("/projects/{project_id}/attach")
def attach_project(
    request: AttachRequest,
    project_id: str = Path(..., description="Project ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Attach a verified project to an agent instance.

    Only verified projects can be attached. The agent will receive
    a structured data object for on-demand data querying.
    """
    record = ProjectService.attach_to_agent(
        session, project_id, request.agent_id
    )
    if not record:
        existing = ProjectService.get_project(session, project_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Project '{project_id}' must be verified before "
                    f"attaching to an agent"
                ),
            )
        raise HTTPException(
            status_code=404, detail=f"Project '{project_id}' not found"
        )
    return {
        "success": True,
        "data": _project_to_dict(record),
        "message": f"Project '{record.name}' attached to agent '{request.agent_id}'",
    }


@router.post("/projects/{project_id}/detach")
def detach_project(
    project_id: str = Path(..., description="Project ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Detach a project from its agent."""
    record = ProjectService.detach_from_agent(session, project_id)
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Project '{project_id}' not found"
        )
    return {
        "success": True,
        "data": _project_to_dict(record),
        "message": f"Project detached from agent",
    }


@router.post("/projects/{project_id}/build-data-object")
def build_data_object(
    project_id: str = Path(..., description="Project ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Build the agent-callable data object for a project.

    Constructs a structured data object that defines all methods,
    sources, and data available for an agent to query on-demand.
    """
    result = ProjectService.build_data_object(session, project_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=404, detail=result.get("error", "Project not found")
        )
    return result


@router.get("/projects/{project_id}/data-object")
def get_data_object(
    project_id: str = Path(..., description="Project ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get the current data object schema for a project."""
    result = ProjectService.get_data_object(session, project_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=404, detail=result.get("error", "Project not found")
        )
    return result


# ═══════════════════════════════════════════════════════════════════
# Duplicate
# ═══════════════════════════════════════════════════════════════════


@router.post("/projects/{project_id}/duplicate", status_code=201)
def duplicate_project(
    request: DuplicateRequest,
    project_id: str = Path(..., description="Project ID to duplicate"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Duplicate a project, optionally including its documents."""
    result = ProjectService.duplicate_project(
        session, project_id, include_docs=request.include_docs,
    )
    if not result:
        raise HTTPException(
            status_code=404, detail=f"Project '{project_id}' not found"
        )
    record, doc_count = result
    ProjectService.log_activity(
        session, project_id=record.id, action="duplicated_from",
        entity_type="project", entity_id=project_id,
        details={"include_docs": request.include_docs, "doc_count": doc_count},
    )
    return {
        "success": True,
        "data": _project_to_dict(record),
        "documents_copied": doc_count,
        "message": f"Project duplicated as '{record.name}' with {doc_count} document(s)",
    }


# ═══════════════════════════════════════════════════════════════════
# Members
# ═══════════════════════════════════════════════════════════════════


@router.get("/projects/{project_id}/members")
def list_members(
    project_id: str = Path(..., description="Project ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List all members of a project."""
    # Verify project exists
    project = ProjectService.get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=404, detail=f"Project '{project_id}' not found"
        )
    members = ProjectService.list_members(session, project_id)
    return {
        "success": True,
        "data": [_member_to_dict(m) for m in members],
        "total": len(members),
    }


@router.post("/projects/{project_id}/members", status_code=201)
def add_member(
    request: AddMemberRequest,
    project_id: str = Path(..., description="Project ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Add a member to a project."""
    record = ProjectService.add_member(
        session, project_id, user_id=request.user_id,
        role=request.role, invited_by="api",
    )
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Project '{project_id}' not found"
        )
    return {
        "success": True,
        "data": _member_to_dict(record),
        "message": f"User '{request.user_id}' added as {request.role}",
    }


@router.delete("/projects/{project_id}/members/{user_id}")
def remove_member(
    project_id: str = Path(..., description="Project ID"),
    user_id: str = Path(..., description="User ID to remove"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Remove a member from a project."""
    deleted = ProjectService.remove_member(session, project_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Member '{user_id}' not found in project '{project_id}'",
        )
    return {
        "success": True,
        "message": f"User '{user_id}' removed from project",
    }


@router.put("/projects/{project_id}/members/{user_id}")
def change_member_role(
    request: ChangeRoleRequest,
    project_id: str = Path(..., description="Project ID"),
    user_id: str = Path(..., description="User ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Change a member's role in a project."""
    record = ProjectService.change_member_role(
        session, project_id, user_id, new_role=request.role,
    )
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Member '{user_id}' not found in project '{project_id}'",
        )
    return {
        "success": True,
        "data": _member_to_dict(record),
        "message": f"User '{user_id}' role changed to '{request.role}'",
    }


# ═══════════════════════════════════════════════════════════════════
# Activity Log
# ═══════════════════════════════════════════════════════════════════


@router.get("/projects/{project_id}/activity")
def list_activity(
    project_id: str = Path(..., description="Project ID"),
    limit: int = Query(50, description="Max entries to return"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List recent activity log entries for a project."""
    project = ProjectService.get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=404, detail=f"Project '{project_id}' not found"
        )
    entries = ProjectService.list_activity(session, project_id, limit=limit)
    return {
        "success": True,
        "data": [_activity_to_dict(e) for e in entries],
        "total": len(entries),
    }


# ── Serialization helpers ─────────────────────────────────────


def _member_to_dict(record: ProjectMemberRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "project_id": record.project_id,
        "user_id": record.user_id,
        "role": record.role,
        "invited_by": record.invited_by,
        "invited_at": record.invited_at.isoformat() if record.invited_at else None,
    }


def _activity_to_dict(record: ActivityLogRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "project_id": record.project_id,
        "user_id": record.user_id,
        "action": record.action,
        "entity_type": record.entity_type,
        "entity_id": record.entity_id,
        "details": record.details,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _project_to_dict(record: KnowledgeProjectRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "description": record.description,
        "status": record.status,
        "verified_at": record.verified_at.isoformat() if record.verified_at else None,
        "packet_ids": record.packet_ids,
        "attached_agent_id": record.attached_agent_id,
        "data_object_schema": record.data_object_schema,
        "tags": record.tags,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
