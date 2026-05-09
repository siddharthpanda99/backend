import logging
from uuid import UUID
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from app.mcp.mcp_dependencies import resolve_daw_service, resolve_db_session

logger = logging.getLogger("mcp.tools.music")

def register_music_tools(mcp: FastMCP):
    """Register all DAW (Digital Audio Workstation) and music production tools."""

    @mcp.tool()
    async def list_music_projects() -> List[Dict[str, Any]]:
        """List all music production projects."""
        service = resolve_daw_service()
        session = resolve_db_session()
        # Using a mock user ID for global platform context
        MOCK_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
        projects = service.get_user_projects(session, MOCK_USER_ID)
        return [p.model_dump() for p in projects]

    @mcp.tool()
    async def get_music_project(project_id: str) -> Dict[str, Any]:
        """Retrieve full details of a DAW project, including channels, patterns, and clips."""
        service = resolve_daw_service()
        session = resolve_db_session()
        project = service.get_project_with_details(session, UUID(project_id))
        if not project:
            return {"status": "error", "message": "Project not found"}
        return project.model_dump()

    @mcp.tool()
    async def add_music_pattern(project_id: str, name: str) -> Dict[str, Any]:
        """Add a new musical pattern to a DAW project."""
        service = resolve_daw_service()
        session = resolve_db_session()
        from common_lib.modules.daw.schemas import PatternCreate
        pattern = service.create_pattern(session, UUID(project_id), PatternCreate(name=name))
        return pattern.model_dump()

    @mcp.tool()
    async def add_music_note(pattern_id: str, pitch: int, velocity: int, start: float, duration: float) -> Dict[str, Any]:
        """Add a MIDI note to a specific pattern. Pitch is MIDI number (0-127)."""
        service = resolve_daw_service()
        session = resolve_db_session()
        from common_lib.modules.daw.schemas import NoteCreate
        note = service.add_note(session, UUID(pattern_id), NoteCreate(
            pitch=pitch, velocity=velocity, start=start, duration=duration
        ))
        return note.model_dump()
