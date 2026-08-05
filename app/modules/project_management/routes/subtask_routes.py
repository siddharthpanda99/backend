"""Subtask Routes — nested task management endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.modules.auth.dependencies import require_permission
from app.modules.project_management.field_security_deps import (
    filter_single_response,
    filter_list_response,
)

router = APIRouter()


def _get_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


# ---------------------------------------------------------------------------
# Request/Response Schemas
# ---------------------------------------------------------------------------

class SubtaskCreateRequest(BaseModel):
    title: str
    description_text: Optional[str] = None
    issue_type_id: Optional[str] = None
    assignee_id: Optional[str] = None
    priority: str = "medium"
    story_points: Optional[float] = None
    time_estimate_minutes: Optional[int] = None
    due_date: Optional[str] = None
    label_ids: List[str] = []
    component_ids: List[str] = []
    created_by: str = "system"


class SubtaskConvertRequest(BaseModel):
    new_parent_id: str


class SubtaskListResponse(BaseModel):
    subtasks: List[Dict[str, Any]]
    total: int


class SubtaskProgressResponse(BaseModel):
    parent_id: str
    total_subtasks: int
    completed_subtasks: int
    in_progress_subtasks: int
    todo_subtasks: int
    progress_percent: float
    total_story_points: Optional[float] = None
    completed_story_points: Optional[float] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/issues/{issue_id}/subtasks", status_code=201)
async def create_subtask(request: Request, issue_id: str, req: SubtaskCreateRequest,
    _perm: None = require_permission("subtask.create", "*", "subtask"),):
    """Create a subtask under a parent issue."""
    from common_lib.modules.project_management.subtasks.service import SubtaskService
    with _get_session() as session:
        svc = SubtaskService(session)
        try:
            subtask = svc.create_subtask(
                parent_id=issue_id,
                data=req,
                created_by="system",
            )
            return {
                "id": subtask.id,
                "key": subtask.key,
                "title": subtask.title,
                "status_id": subtask.status_id,
                "parent_id": subtask.parent_id,
            }
        except (ValueError, Exception) as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.get("/issues/{issue_id}/subtasks")
async def list_subtasks(request: Request, issue_id: str, include_archived: bool = False,
    _perm: None = require_permission("subtask.read", "*", "subtask"),):
    """List all subtasks of a parent issue."""
    from common_lib.modules.project_management.subtasks.service import SubtaskService
    with _get_session() as session:
        svc = SubtaskService(session)
        subtasks = svc.list_subtasks(issue_id, include_archived=include_archived)
        return {
            "subtasks": [
                {
                    "id": s.id,
                    "key": s.key,
                    "sequence_number": s.sequence_number,
                    "title": s.title,
                    "status_id": s.status_id,
                    "priority": s.priority,
                    "assignee_id": s.assignee_id,
                    "story_points": s.story_points,
                    "due_date": str(s.due_date) if s.due_date else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    "is_archived": s.is_archived,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in subtasks
            ],
            "total": len(subtasks),
        }


@router.get("/issues/{issue_id}/subtasks/progress")
async def get_subtask_progress(request: Request, issue_id: str,
    _perm: None = require_permission("subtask.read", "*", "subtask"),):
    """Get progress rollup for an issue's subtasks."""
    from common_lib.modules.project_management.subtasks.service import SubtaskService
    with _get_session() as session:
        svc = SubtaskService(session)
        progress = svc.get_progress(issue_id)
        return {
            "parent_id": progress.get("parent_id", issue_id),
            "total_subtasks": progress.get("total_subtasks", 0),
            "completed_subtasks": progress.get("completed_subtasks", 0),
            "in_progress_subtasks": progress.get("in_progress_subtasks", 0),
            "todo_subtasks": progress.get("todo_subtasks", 0),
            "progress_percent": progress.get("progress_percent", 0.0),
            "total_story_points": progress.get("total_story_points"),
            "completed_story_points": progress.get("completed_story_points"),
        }


@router.put("/issues/{issue_id}/subtasks/convert/{subtask_id}")
async def convert_to_subtask(request: Request, issue_id: str, subtask_id: str,
    _perm: None = require_permission("subtask.update", "*", "subtask"),):
    """Convert an existing issue into a subtask of issue_id."""
    from common_lib.modules.project_management.subtasks.service import SubtaskService
    with _get_session() as session:
        svc = SubtaskService(session)
        try:
            result = svc.convert_to_subtask(subtask_id, issue_id)
            if not result:
                raise HTTPException(status_code=404, detail="Issue not found")
            return {"id": result.id, "key": result.key, "parent_id": result.parent_id}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.delete("/subtasks/{subtask_id}")
async def remove_subtask(request: Request, subtask_id: str, unlink: bool = False,
    _perm: None = require_permission("subtask.delete", "*", "subtask"),):
    """Remove a subtask — archive it (default) or unlink from parent."""
    from common_lib.modules.project_management.subtasks.service import SubtaskService
    with _get_session() as session:
        svc = SubtaskService(session)
        result = svc.remove_subtask(subtask_id, unlink=unlink)
        if not result:
            raise HTTPException(status_code=404, detail="Subtask not found")
        return {"success": True, "subtask_id": subtask_id}
