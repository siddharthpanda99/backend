"""Evolver Audit routes — structured session audit log."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from app.modules.common.types.index import APIResponse

router = APIRouter(prefix="/audit", tags=["Evolver Audit"])


class AuditCreateRequest(BaseModel):
    session_id: str
    level: str = "info"
    category: str = "general"
    message: str
    details: str = ""
    agent_id: Optional[str] = None
    tool_name: Optional[str] = None


@router.post("", response_model=APIResponse[Dict[str, Any]])
async def create_audit_entry(req: AuditCreateRequest):
    """Create a new audit log entry."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
            AuditEntryService,
        )

        svc = AuditEntryService()
        entry = svc.create(
            session_id=req.session_id,
            level=req.level,
            category=req.category,
            message=req.message,
            details=req.details,
            agent_id=req.agent_id,
            tool_name=req.tool_name,
        )
        return APIResponse(data=entry.model_dump(), message="Audit entry created")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}", response_model=APIResponse[List[Dict[str, Any]]])
async def get_audit_log(
    session_id: str,
    level: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """Get audit log entries for a session."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
            AuditEntryService,
        )

        svc = AuditEntryService()
        entries = svc.list_by_session(
            session_id=session_id,
            level=level,
            category=category,
            limit=limit,
            offset=offset,
        )
        return APIResponse(
            data=[e.model_dump() for e in entries], message="Audit entries retrieved"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}", response_model=APIResponse)
async def clear_audit_log(session_id: str):
    """Clear all audit entries for a session."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
            AuditEntryService,
        )

        svc = AuditEntryService()
        count = svc.delete_by_session(session_id)
        return APIResponse(data=None, message=f"Deleted {count} audit entries")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
