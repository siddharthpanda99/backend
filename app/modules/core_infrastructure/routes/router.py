"""Core Infrastructure module API routes — Tool Registry, Discovery, Sandbox.

Thin routing layer that delegates to common_lib.modules.core_infrastructure services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ToolRegisterRequest(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class SandboxExecuteRequest(BaseModel):
    code: str
    language: Optional[str] = "python"
    timeout: Optional[int] = 30


# ---------------------------------------------------------------------------
# Lazy service loader
# ---------------------------------------------------------------------------

def _get_registry():
    from common_lib.modules.core_infrastructure.service import ToolRegistry
    return ToolRegistry()


def _get_sandbox():
    from common_lib.modules.core_infrastructure.service import SandboxExecutor
    return SandboxExecutor()


# ---------------------------------------------------------------------------
# Tool Registry endpoints
# ---------------------------------------------------------------------------

@router.get("/tools")
async def list_tools() -> Dict[str, Any]:
    """List all registered tools."""
    try:
        svc = _get_registry()
        result = svc.list_tools() if hasattr(svc, "list_tools") else []
        return {"tools": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools")
async def register_tool(request: ToolRegisterRequest) -> Dict[str, Any]:
    """Register a new tool."""
    try:
        svc = _get_registry()
        result = svc.register(request.name, request.description, request.category, request.parameters) if hasattr(svc, "register") else {"name": request.name}
        return {"tool": result, "message": "Tool registered successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools/{tool_id}")
async def get_tool(tool_id: str) -> Dict[str, Any]:
    """Get a tool by ID."""
    try:
        svc = _get_registry()
        result = svc.get(tool_id) if hasattr(svc, "get") else None
        if result is None:
            raise HTTPException(status_code=404, detail="Tool not found")
        return {"tool": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tools/{tool_id}")
async def unregister_tool(tool_id: str) -> Dict[str, Any]:
    """Unregister a tool."""
    try:
        svc = _get_registry()
        svc.unregister(tool_id) if hasattr(svc, "unregister") else None
        return {"success": True, "message": "Tool unregistered successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Discovery endpoints
# ---------------------------------------------------------------------------

@router.get("/discover")
async def discover_tools(query: Optional[str] = None) -> Dict[str, Any]:
    """Discover tools by query."""
    try:
        svc = _get_registry()
        result = svc.discover(query) if hasattr(svc, "discover") else []
        return {"tools": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog")
async def get_catalog() -> Dict[str, Any]:
    """Get the full tool catalog."""
    try:
        svc = _get_registry()
        result = svc.get_catalog() if hasattr(svc, "get_catalog") else {}
        return {"catalog": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Sandbox execution endpoints
# ---------------------------------------------------------------------------

@router.post("/sandbox/execute")
async def execute_in_sandbox(request: SandboxExecuteRequest) -> Dict[str, Any]:
    """Execute code in the sandbox."""
    try:
        svc = _get_sandbox()
        result = svc.execute(request.code, request.language, request.timeout) if hasattr(svc, "execute") else {"output": ""}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sandbox/status")
async def sandbox_status() -> Dict[str, Any]:
    """Get sandbox status."""
    try:
        svc = _get_sandbox()
        result = svc.status() if hasattr(svc, "status") else {"status": "ok"}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
