# DAW Routes - REST API for DAW projects
from fastapi import APIRouter, HTTPException, Depends, Depends
from uuid import UUID
from typing import List, Annotated
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.daw.schemas import (
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
from common_lib.modules.daw.service import daw_service, NotFoundError

MOCK_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

router = APIRouter(prefix="/daw", tags=["DAW"])


@router.post("/projects", response_model=DAWProjectResponse)
async def create_project(
    data: DAWProjectCreate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.create_project(session, MOCK_USER_ID, data)


@router.get("/projects", response_model=List[DAWProjectResponse])
async def list_projects(
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.get_user_projects(session, MOCK_USER_ID)


@router.get("/projects/{project_id}", response_model=DAWProjectResponse)
async def get_project(
    project_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    project = daw_service.get_project_with_details(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/projects/{project_id}", response_model=DAWProjectResponse)
async def update_project(
    project_id: UUID,
    data: DAWProjectUpdate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.update_project(session, project_id, data)


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    daw_service.delete(session, project_id)
    return {"status": "deleted"}


@router.post("/projects/{project_id}/channels", response_model=ChannelResponse)
async def create_channel(
    project_id: UUID,
    data: ChannelCreate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.create_channel(session, project_id, data)


@router.patch("/channels/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: UUID,
    data: ChannelUpdate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.update_channel(session, channel_id, data)


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    daw_service.delete_channel(session, channel_id)
    return {"status": "deleted"}


@router.post("/projects/{project_id}/patterns", response_model=PatternResponse)
async def create_pattern(
    project_id: UUID,
    data: PatternCreate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.create_pattern(session, project_id, data)


@router.patch("/patterns/{pattern_id}", response_model=PatternResponse)
async def update_pattern(
    pattern_id: UUID,
    data: PatternUpdate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.update_pattern(session, pattern_id, data)


@router.post("/patterns/{pattern_id}/notes", response_model=NoteResponse)
async def add_note(
    pattern_id: UUID,
    data: NoteCreate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.add_note(session, pattern_id, data)


@router.patch("/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: UUID,
    data: NoteUpdate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.update_note(session, note_id, data)


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    daw_service.delete_note(session, note_id)
    return {"status": "deleted"}


@router.post("/projects/{project_id}/clips", response_model=ClipResponse)
async def create_clip(
    project_id: UUID,
    data: ClipCreate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.create_clip(session, project_id, data)


@router.patch("/clips/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: UUID,
    data: ClipUpdate,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.update_clip(session, clip_id, data)


@router.delete("/clips/{clip_id}")
async def delete_clip(
    clip_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    daw_service.delete_clip(session, clip_id)
    return {"status": "deleted"}


@router.get("/projects/{project_id}/export", response_model=DAWExport)
async def export_project(
    project_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    return daw_service.export_project(session, project_id)


__all__ = ["router"]
