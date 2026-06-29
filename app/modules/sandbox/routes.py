"""
Sandbox API — Execute Python code in ephemeral Docker containers.

/api/v1/sandbox/execute — one-shot code execution (create + run + destroy)
/api/v1/sandbox/sessions — managed session lifecycle
/api/v1/sandbox/health — check provider health
"""

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from common_lib.modules.sandbox.sandbox_service import get_sandbox_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sandbox", tags=["Sandbox"])


# ─── Schemas ────────────────────────────────────────────────────────


class ExecuteRequest(BaseModel):
    code: str = Field(..., description="Python code to execute")
    language: str = Field("python", description="Language (python or bash)")
    image: str = Field("python:3.12-slim", description="Docker image")
    timeout: float = Field(
        30.0, ge=1, le=120, description="Max execution time in seconds"
    )
    inject_keys: bool = Field(False, description="Inject API keys from connector store")


class ExecuteResponse(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_ms: float = 0.0
    timed_out: bool = False
    error: Optional[str] = None


class SessionCreateRequest(BaseModel):
    image: str = Field("python:3.12-slim")
    timeout: float = Field(30.0, ge=1, le=120)
    memory_limit_mb: int = Field(512, ge=64, le=4096)
    cpu_limit: float = Field(1.0, ge=0.1, le=8.0)
    network_enabled: bool = False
    inject_keys: bool = False


class SessionExecuteRequest(BaseModel):
    code: str = Field(..., description="Code to execute in session")
    language: str = Field("python")
    timeout: Optional[float] = Field(None, ge=1, le=120)


class SessionResponse(BaseModel):
    session_id: str
    status: str
    created_at: float = 0.0
    last_active: float = 0.0
    metadata: Dict[str, Any] = {}


class HealthResponse(BaseModel):
    healthy: bool
    provider: str = "unknown"
    sessions_active: int = 0


# ─── Routes ─────────────────────────────────────────────────────────


@router.post("/execute", response_model=ExecuteResponse)
async def execute_code(data: ExecuteRequest):
    """
    Execute Python code in a fresh Docker container.
    Container is created, code is run, container is destroyed.
    """
    svc = get_sandbox_service()
    if not svc._initialized:
        await svc.initialize()

    result = await svc.execute_code(
        code=data.code,
        language=data.language,
        image=data.image,
        timeout=data.timeout,
        inject_keys=data.inject_keys,
    )

    return ExecuteResponse(
        success=result.exit_code == 0,
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
        timed_out=result.timed_out,
        error=result.error,
    )


@router.post("/sessions", response_model=SessionResponse)
async def create_session(data: SessionCreateRequest):
    """Create a persistent sandbox session (container stays alive)."""
    svc = get_sandbox_service()
    if not svc._initialized:
        await svc.initialize()

    try:
        session = await svc.create_session(
            image=data.image,
            timeout=data.timeout,
            memory_limit_mb=data.memory_limit_mb,
            cpu_limit=data.cpu_limit,
            network_enabled=data.network_enabled,
            inject_keys=data.inject_keys,
        )
        return SessionResponse(
            session_id=session.session_id,
            status=session.status,
            created_at=session.created_at,
            last_active=session.last_active,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {e}")


@router.post("/sessions/{session_id}/exec", response_model=ExecuteResponse)
async def execute_in_session(session_id: str, data: SessionExecuteRequest):
    """Execute code in an existing sandbox session."""
    svc = get_sandbox_service()
    if not svc._initialized:
        await svc.initialize()

    result = await svc.execute(
        session_id=session_id,
        code=data.code,
        language=data.language,
        timeout=data.timeout,
    )

    return ExecuteResponse(
        success=result.exit_code == 0,
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
        timed_out=result.timed_out,
        error=result.error,
    )


@router.delete("/sessions/{session_id}", response_model=Dict[str, Any])
async def destroy_session(session_id: str):
    """Destroy a sandbox session (kill container)."""
    svc = get_sandbox_service()
    if not svc._initialized:
        await svc.initialize()

    ok = await svc.destroy_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {"success": True, "session_id": session_id}


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    """List all active sandbox sessions."""
    svc = get_sandbox_service()
    if not svc._initialized:
        await svc.initialize()

    sessions = await svc.list_sessions()
    return [
        SessionResponse(
            session_id=s.session_id,
            status=s.status,
            created_at=s.created_at,
            last_active=s.last_active,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get details for a specific sandbox session."""
    svc = get_sandbox_service()
    if not svc._initialized:
        await svc.initialize()

    session = await svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return SessionResponse(
        session_id=session.session_id,
        status=session.status,
        created_at=session.created_at,
        last_active=session.last_active,
    )


@router.get("/health", response_model=HealthResponse)
async def sandbox_health():
    """Check sandbox provider health."""
    svc = get_sandbox_service()
    if not svc._initialized:
        await svc.initialize()

    healthy = await svc.health_check()
    sessions = await svc.list_sessions()
    provider_type = (
        "docker"
        if svc._provider and "Docker" in type(svc._provider).__name__
        else "process"
    )

    return HealthResponse(
        healthy=healthy,
        provider=provider_type,
        sessions_active=len(sessions),
    )
