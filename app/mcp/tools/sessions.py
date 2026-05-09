import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from ..mcp_dependencies import resolve_session_service

logger = logging.getLogger("mcp.tools.sessions")

def register_session_tools(mcp: FastMCP):
    """Register tools for managing active chat and orchestration sessions."""

    @mcp.tool()
    async def list_sessions(active_only: bool = True) -> List[Dict[str, Any]]:
        """List all active agent and user sessions."""
        service = resolve_session_service()
        sessions = await service.get_sessions(active_only=active_only)
        return [s.model_dump() for s in sessions]

    @mcp.tool()
    async def get_session_details(session_id: str) -> Dict[str, Any]:
        """Retrieve detailed metrics and history for a specific session."""
        service = resolve_session_service()
        session = await service.get_session(session_id)
        if not session:
            return {"status": "error", "message": "Session not found"}
        return session.model_dump()

    @mcp.tool()
    async def terminate_session(session_id: str) -> Dict[str, Any]:
        """[DESTRUCTIVE] Forcefully terminate an active session."""
        service = resolve_session_service()
        try:
            await service.terminate_session(session_id)
            return {"status": "terminated", "session_id": session_id}
        except Exception as e:
            return {"status": "error", "message": str(e)}
