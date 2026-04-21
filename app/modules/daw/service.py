# DAW Service - Business logic for DAW projects
from sqlmodel import select, and_, delete as sql_delete
from uuid import UUID, uuid4
from datetime import datetime
from typing import List, Optional
import json

from app.modules.database.service.connection import get_session
from .models import (
    DAWProject,
    Channel,
    Pattern,
    Note,
    Clip,
    ProjectStatus,
    steps_to_string,
    steps_from_string,
    time_signature_to_string,
    time_signature_from_string,
)

Project = DAWProject  # Alias
from .schemas import (
    DAWProjectCreate,
    DAWProjectUpdate,
    ChannelCreate,
    ChannelUpdate,
    PatternCreate,
    PatternUpdate,
    NoteCreate,
    NoteUpdate,
    ClipCreate,
    ClipUpdate,
)


class NotFoundError(Exception):
    """Resource not found"""

    pass


from .models import DAWProject, Channel, Pattern, Note, Clip, ProjectStatus

Project = DAWProject  # Alias for backward compatibility

from .schemas import (
    DAWProjectCreate,
    DAWProjectUpdate,
    ChannelCreate,
    ChannelUpdate,
    PatternCreate,
    PatternUpdate,
    NoteCreate,
    NoteUpdate,
    ClipCreate,
    ClipUpdate,
)


class DAWService:
    # Project CRUD
    async def create_project(self, user_id: UUID, data: DAWProjectCreate) -> Project:
        async with get_session() as session:
            project = Project(
                id=uuid4(),
                name=data.name,
                description=data.description,
                user_id=user_id,
                bpm=data.bpm,
                time_signature=time_signature_to_string(data.time_signature),
                master_volume=data.master_volume,
                status=ProjectStatus.DRAFT,
            )
            session.add(project)
            await session.flush()
            await session.refresh(project)

            # Create default pattern
            pattern = Pattern(
                id=uuid4(),
                name="Pattern 1",
                length=16,
                project_id=project.id,
            )
            session.add(pattern)

            # Create default channels
            default_channels = [
                (
                    "Kick",
                    "drum",
                    "#ef4444",
                    [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
                ),
                (
                    "Snare",
                    "drum",
                    "#f59e0b",
                    [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
                ),
                (
                    "Clap",
                    "drum",
                    "#10b981",
                    [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
                ),
                (
                    "Hi-Hat",
                    "drum",
                    "#8b5cf6",
                    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                ),
                (
                    "Synth",
                    "synth",
                    "#3b82f6",
                    [1, 0, 1, 0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 0],
                ),
                (
                    "Bass",
                    "bass",
                    "#ec4899",
                    [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
                ),
            ]

            for idx, (name, ch_type, color, steps) in enumerate(default_channels):
                channel = Channel(
                    id=uuid4(),
                    name=name,
                    type=ch_type,
                    color=color,
                    steps=steps_to_string(steps),
                    project_id=project.id,
                    order_index=idx,
                )
                session.add(channel)

            await session.commit()
            return project

    async def get(self, project_id: UUID) -> Optional[Project]:
        async with get_session() as session:
            stmt = select(Project).where(Project.id == project_id)
            result = await session.exec(stmt)
            return result.first()

    async def get_user_projects(self, user_id: UUID) -> List[Project]:
        async with get_session() as session:
            stmt = (
                select(Project)
                .where(Project.user_id == user_id)
                .order_by(Project.updated_at.desc())
            )
            result = await session.exec(stmt)
            return result.all()

    async def get_project_with_details(self, project_id: UUID) -> Optional[Project]:
        async with get_session() as session:
            stmt = select(Project).where(Project.id == project_id)
            result = await session.exec(stmt)
            return result.first()

    async def update_project(self, project_id: UUID, data: DAWProjectUpdate) -> Project:
        async with get_session() as session:
            stmt = select(Project).where(Project.id == project_id)
            result = await session.exec(stmt)
            project = result.first()

            if not project:
                raise NotFoundError(f"Project {project_id} not found")

            if data.name is not None:
                project.name = data.name
            if data.description is not None:
                project.description = data.description
            if data.bpm is not None:
                project.bpm = data.bpm
            if data.master_volume is not None:
                project.master_volume = data.master_volume
            if data.status is not None:
                project.status = data.status

            project.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(project)
            return project

    async def delete(self, project_id: UUID) -> None:
        async with get_session() as session:
            stmt = select(Project).where(Project.id == project_id)
            result = await session.exec(stmt)
            project = result.first()
            if project:
                await session.delete(project)
                await session.commit()

    # Channel CRUD
    async def create_channel(self, project_id: UUID, data: ChannelCreate) -> Channel:
        async with get_session() as session:
            stmt = select(Channel).where(Channel.project_id == project_id)
            result = await session.exec(stmt)
            channels = result.all()
            max_order = max([c.order_index for c in channels]) if channels else -1

            channel = Channel(
                id=uuid4(),
                name=data.name,
                type=data.type,
                color=data.color,
                volume=data.volume,
                pan=data.pan,
                mute=data.mute,
                solo=data.solo,
                steps=steps_to_string(data.steps),
                project_id=project_id,
                order_index=max_order + 1,
            )
            session.add(channel)
            await session.commit()
            await session.refresh(channel)
            return channel

    async def update_channel(self, channel_id: UUID, data: ChannelUpdate) -> Channel:
        async with get_session() as session:
            stmt = select(Channel).where(Channel.id == channel_id)
            result = await session.exec(stmt)
            channel = result.first()

            if not channel:
                raise NotFoundError(f"Channel {channel_id} not found")

            if data.name is not None:
                channel.name = data.name
            if data.color is not None:
                channel.color = data.color
            if data.volume is not None:
                channel.volume = data.volume
            if data.pan is not None:
                channel.pan = data.pan
            if data.mute is not None:
                channel.mute = data.mute
            if data.solo is not None:
                channel.solo = data.solo
            if data.steps is not None:
                channel.steps = steps_to_string(data.steps)

            await session.commit()
            await session.refresh(channel)
            return channel

    async def delete_channel(self, channel_id: UUID) -> None:
        async with get_session() as session:
            stmt = select(Channel).where(Channel.id == channel_id)
            result = await session.exec(stmt)
            channel = result.first()
            if channel:
                await session.delete(channel)
                await session.commit()

    # Pattern CRUD
    async def create_pattern(self, project_id: UUID, data: PatternCreate) -> Pattern:
        async with get_session() as session:
            pattern = Pattern(
                id=uuid4(),
                name=data.name,
                length=data.length,
                project_id=project_id,
            )
            session.add(pattern)
            await session.commit()
            await session.refresh(pattern)
            return pattern

    async def update_pattern(self, pattern_id: UUID, data: PatternUpdate) -> Pattern:
        async with get_session() as session:
            stmt = select(Pattern).where(Pattern.id == pattern_id)
            result = await session.exec(stmt)
            pattern = result.first()

            if not pattern:
                raise NotFoundError(f"Pattern {pattern_id} not found")

            if data.name is not None:
                pattern.name = data.name
            if data.length is not None:
                pattern.length = data.length

            pattern.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(pattern)
            return pattern

    # Note CRUD
    async def add_note(self, pattern_id: UUID, data: NoteCreate) -> Note:
        async with get_session() as session:
            note = Note(
                id=uuid4(),
                pitch=data.pitch,
                start=data.start,
                duration=data.duration,
                velocity=data.velocity,
                pattern_id=pattern_id,
                channel_id=data.channel_id,
            )
            session.add(note)
            await session.commit()
            await session.refresh(note)
            return note

    async def update_note(self, note_id: UUID, data: NoteUpdate) -> Note:
        async with get_session() as session:
            stmt = select(Note).where(Note.id == note_id)
            result = await session.exec(stmt)
            note = result.first()

            if not note:
                raise NotFoundError(f"Note {note_id} not found")

            if data.pitch is not None:
                note.pitch = data.pitch
            if data.start is not None:
                note.start = data.start
            if data.duration is not None:
                note.duration = data.duration
            if data.velocity is not None:
                note.velocity = data.velocity

            await session.commit()
            await session.refresh(note)
            return note

    async def delete_note(self, note_id: UUID) -> None:
        async with get_session() as session:
            stmt = select(Note).where(Note.id == note_id)
            result = await session.exec(stmt)
            note = result.first()
            if note:
                await session.delete(note)
                await session.commit()

    # Clip CRUD
    async def create_clip(self, project_id: UUID, data: ClipCreate) -> Clip:
        async with get_session() as session:
            clip = Clip(
                id=uuid4(),
                pattern_id=data.pattern_id,
                channel_id=data.channel_id,
                project_id=project_id,
                start=data.start,
                length=data.length,
            )
            session.add(clip)
            await session.commit()
            await session.refresh(clip)
            return clip

    async def update_clip(self, clip_id: UUID, data: ClipUpdate) -> Clip:
        async with get_session() as session:
            stmt = select(Clip).where(Clip.id == clip_id)
            result = await session.exec(stmt)
            clip = result.first()

            if not clip:
                raise NotFoundError(f"Clip {clip_id} not found")

            if data.start is not None:
                clip.start = data.start
            if data.length is not None:
                clip.length = data.length

            await session.commit()
            await session.refresh(clip)
            return clip

    async def delete_clip(self, clip_id: UUID) -> None:
        async with get_session() as session:
            stmt = select(Clip).where(Clip.id == clip_id)
            result = await session.exec(stmt)
            clip = result.first()
            if clip:
                await session.delete(clip)
                await session.commit()


# Singleton
daw_service = DAWService()

__all__ = ["DAWService", "daw_service"]
