# DAW Routes - REST API for DAW projects
from fastapi import APIRouter, HTTPException
from uuid import UUID
from typing import List
from .service import daw_service
from .schemas import (
    DAWProjectCreate,
    DAWProjectUpdate,
    DAWProjectResponse,
    ChannelCreate,
    ChannelUpdate,
    ChannelResponse,
    PatternCreate,
    PatternUpdate,
    PatternResponse,
    NoteCreate,
    NoteUpdate,
    NoteResponse,
    ClipCreate,
    ClipUpdate,
    ClipResponse,
    DAWExport,
)
from typing import Optional

# Mock user for now - in production this would come from auth
MOCK_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


router = APIRouter(prefix="/daw", tags=["DAW"])


# Project endpoints
@router.post("/projects", response_model=DAWProjectResponse)
async def create_project(data: DAWProjectCreate):
    """Create a new DAW project with default channels and patterns."""
    return await daw_service.create_project(MOCK_USER_ID, data)


@router.get("/projects", response_model=List[DAWProjectResponse])
async def list_projects():
    """List all projects for the current user."""
    return await daw_service.get_user_projects(MOCK_USER_ID)


@router.get("/projects/{project_id}", response_model=DAWProjectResponse)
async def get_project(project_id: UUID):
    """Get a project with all details."""
    project = await daw_service.get_project_with_details(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/projects/{project_id}", response_model=DAWProjectResponse)
async def update_project(project_id: UUID, data: DAWProjectUpdate):
    """Update project settings."""
    return await daw_service.update_project(project_id, data)


@router.delete("/projects/{project_id}")
async def delete_project(project_id: UUID):
    """Delete a project."""
    await daw_service.delete(project_id)
    return {"status": "deleted"}


# Channel endpoints
@router.post("/projects/{project_id}/channels", response_model=ChannelResponse)
async def create_channel(project_id: UUID, data: ChannelCreate):
    """Add a channel to a project."""
    return await daw_service.create_channel(project_id, data)


@router.patch("/channels/{channel_id}", response_model=ChannelResponse)
async def update_channel(channel_id: UUID, data: ChannelUpdate):
    """Update a channel."""
    return await daw_service.update_channel(channel_id, data)


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: UUID):
    """Delete a channel."""
    await daw_service.delete_channel(channel_id)
    return {"status": "deleted"}


# Pattern endpoints
@router.post("/projects/{project_id}/patterns", response_model=PatternResponse)
async def create_pattern(project_id: UUID, data: PatternCreate):
    """Add a pattern to a project."""
    return await daw_service.create_pattern(project_id, data)


@router.patch("/patterns/{pattern_id}", response_model=PatternResponse)
async def update_pattern(pattern_id: UUID, data: PatternUpdate):
    """Update a pattern."""
    return await daw_service.update_pattern(pattern_id, data)


# Note endpoints
@router.post("/patterns/{pattern_id}/notes", response_model=NoteResponse)
async def add_note(pattern_id: UUID, data: NoteCreate):
    """Add a note to a pattern."""
    return await daw_service.add_note(pattern_id, data)


@router.patch("/notes/{note_id}", response_model=NoteResponse)
async def update_note(note_id: UUID, data: NoteUpdate):
    """Update a note."""
    return await daw_service.update_note(note_id, data)


@router.delete("/notes/{note_id}")
async def delete_note(note_id: UUID):
    """Delete a note."""
    await daw_service.delete_note(note_id)
    return {"status": "deleted"}


# Clip endpoints
@router.post("/projects/{project_id}/clips", response_model=ClipResponse)
async def create_clip(project_id: UUID, data: ClipCreate):
    """Add a clip to a project."""
    return await daw_service.create_clip(project_id, data)


@router.patch("/clips/{clip_id}", response_model=ClipResponse)
async def update_clip(clip_id: UUID, data: ClipUpdate):
    """Update a clip."""
    return await daw_service.update_clip(clip_id, data)


@router.delete("/clips/{clip_id}")
async def delete_clip(clip_id: UUID):
    """Delete a clip."""
    await daw_service.delete_clip(clip_id)
    return {"status": "deleted"}


# Export/Import
@router.get("/projects/{project_id}/export", response_model=DAWExport)
async def export_project(project_id: UUID):
    """Export project as JSON."""
    return await daw_service.export_project(project_id)


__all__ = ["router"]
