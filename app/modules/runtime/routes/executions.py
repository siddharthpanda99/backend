"""Runtime Executions Router — GET /runtime/executions/{id}, POST /runtime/executions/{id}/cancel

Thin FastAPI router for execution status and cancellation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/executions", tags=["Runtime — Executions"])


# In-memory execution store (in production, use Redis/DB)
_executions: dict[str, dict[str, Any]] = {}


# ──────────────────────────────────────────────────────────────────
# Request / Response Schemas
# ──────────────────────────────────────────────────────────────────

class ExecutionStatus(BaseModel):
    """Execution status response."""

    execution_id: str
    plan_id: Optional[str] = None
    model_id: str
    request_id: Optional[str] = None
    status: str  # pending, running, completed, failed, cancelled
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output: Optional[Any] = None
    metrics: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    progress: Optional[dict[str, Any]] = None


class CancelRequest(BaseModel):
    """Request to cancel an execution."""

    reason: str = Field(default="user_requested", description="Cancellation reason")


class CancelResponse(BaseModel):
    """Response for cancellation."""

    execution_id: str
    status: str
    message: str


# ──────────────────────────────────────────────────────────────────
# Route Handlers
# ──────────────────────────────────────────────────────────────────

@router.get("", summary="List Executions")
async def list_executions(
    model_id: Optional[str] = Query(default=None, description="Filter by model ID"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=100, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> dict[str, Any]:
    """List executions with optional filters."""
    try:
        filtered = []
        for exec_data in _executions.values():
            if model_id and exec_data.get("model_id") != model_id:
                continue
            if status and exec_data.get("status") != status:
                continue
            filtered.append(exec_data)

        # Sort by created_at descending
        filtered.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        total = len(filtered)
        paginated = filtered[offset:offset + limit]

        return {
            "executions": paginated,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as exc:
        logger.error("list_executions failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{execution_id}", response_model=ExecutionStatus, summary="Get Execution Status")
async def get_execution(execution_id: str = Path(..., description="Execution identifier")) -> ExecutionStatus:
    """Get the status and results of an execution."""
    try:
        if execution_id not in _executions:
            raise HTTPException(status_code=404, detail=f"Execution not found: {execution_id}")

        exec_data = _executions[execution_id]
        return ExecutionStatus(**exec_data)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_execution failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{execution_id}/cancel", response_model=CancelResponse, summary="Cancel Execution")
async def cancel_execution(
    execution_id: str = Path(..., description="Execution identifier"),
    request: CancelRequest = Body(default=CancelRequest()),
) -> CancelResponse:
    """Cancel a running execution."""
    try:
        if execution_id not in _executions:
            raise HTTPException(status_code=404, detail=f"Execution not found: {execution_id}")

        exec_data = _executions[execution_id]
        current_status = exec_data.get("status", "unknown")

        if current_status in ["completed", "failed", "cancelled"]:
            return CancelResponse(
                execution_id=execution_id,
                status=current_status,
                message=f"Execution already {current_status}",
            )

        # Mark as cancelled
        exec_data["status"] = "cancelled"
        exec_data["completed_at"] = datetime.utcnow().isoformat()
        exec_data["error"] = f"Cancelled: {request.reason}"

        # In a real implementation, we would signal the running task to cancel
        # For now, we just update the status

        return CancelResponse(
            execution_id=execution_id,
            status="cancelled",
            message=f"Execution cancelled: {request.reason}",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("cancel_execution failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{execution_id}", summary="Delete Execution Record")
async def delete_execution(execution_id: str = Path(..., description="Execution identifier")) -> dict[str, str]:
    """Delete an execution record from the store."""
    try:
        if execution_id not in _executions:
            raise HTTPException(status_code=404, detail=f"Execution not found: {execution_id}")

        del _executions[execution_id]

        return {"status": "deleted", "execution_id": execution_id}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("delete_execution failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────────────────────────
# Internal Helper Functions (for use by execute router)
# ──────────────────────────────────────────────────────────────────

def create_execution_record(
    execution_id: str,
    model_id: str,
    plan_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a new execution record."""
    record = {
        "execution_id": execution_id,
        "plan_id": plan_id,
        "model_id": model_id,
        "request_id": request_id,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
        "output": None,
        "metrics": None,
        "error": None,
        "progress": None,
    }
    _executions[execution_id] = record
    return record


def update_execution_status(
    execution_id: str,
    status: str,
    output: Any = None,
    metrics: dict[str, Any] = None,
    error: str = None,
    progress: dict[str, Any] = None,
) -> bool:
    """Update an execution record."""
    if execution_id not in _executions:
        return False

    record = _executions[execution_id]
    record["status"] = status

    if status == "running" and not record["started_at"]:
        record["started_at"] = datetime.utcnow().isoformat()

    if status in ["completed", "failed", "cancelled"]:
        record["completed_at"] = datetime.utcnow().isoformat()

    if output is not None:
        record["output"] = output
    if metrics is not None:
        record["metrics"] = metrics
    if error is not None:
        record["error"] = error
    if progress is not None:
        record["progress"] = progress

    return True


def get_execution_record(execution_id: str) -> Optional[dict[str, Any]]:
    """Get an execution record."""
    return _executions.get(execution_id)


# Export helpers for other routers
__all__ = [
    "router",
    "create_execution_record",
    "update_execution_status",
    "get_execution_record",
]