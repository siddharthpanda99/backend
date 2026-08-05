"""FastAPI routes for RBAC Debug/Diff Tools — Permission tracing and role comparison."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["rbac-debug"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class TraceRequest(BaseModel):
    user_id: int
    permission_name: str
    resource_id: Optional[str] = None


class DiffRolesRequest(BaseModel):
    role_id_a: int
    role_id_b: int


class DiffUsersRequest(BaseModel):
    user_id_a: int
    user_id_b: int


@router.post("/trace")
async def trace_permission(request: TraceRequest) -> Dict[str, Any]:
    """Trace WHY a user was allowed or denied a specific permission. Returns step-by-step reasoning."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.debug.service import PermissionDebugger
        debugger = PermissionDebugger(session)
        trace = debugger.trace_permission(
            user_id=request.user_id,
            permission_name=request.permission_name,
            resource_id=request.resource_id,
        )
        return {
            "decision": trace.decision,
            "reason": trace.reason,
            "steps": trace.steps,
            "sources": trace.sources,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/diff-roles")
async def diff_roles(request: DiffRolesRequest) -> Dict[str, Any]:
    """Compare two roles and show their permission differences."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.debug.service import RoleDiffer
        differ = RoleDiffer(session)
        diff = differ.diff_roles(role_id_a=request.role_id_a, role_id_b=request.role_id_b)
        return {
            "added": diff.added,
            "removed": diff.removed,
            "common": diff.common,
            "source_role": diff.source_role,
            "target_role": diff.target_role,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/diff-users")
async def diff_users(request: DiffUsersRequest) -> Dict[str, Any]:
    """Compare the effective permission sets of two users through their assigned roles."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.debug.service import RoleDiffer
        differ = RoleDiffer(session)
        result = differ.diff_users(user_id_a=request.user_id_a, user_id_b=request.user_id_b)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
