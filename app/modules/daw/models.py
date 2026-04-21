# DAW Models - SQLModel database models
# Note: Tables are managed by alembic migration, not create_all()
from sqlmodel import SQLModel, Field, Relationship
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional, List
from enum import Enum


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ChannelType(str, Enum):
    DRUM = "drum"
    SYNTH = "synth"
    BASS = "bass"
    PAD = "pad"
    AUDIO = "audio"
    MIDI = "midi"


class Note(SQLModel, table=True):
    __tablename__ = "daw_note"
    __table_args__ = {"schema": "daw", "extend_existing": True}

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    pitch: int = Field(ge=0, le=127)
    start: int = Field(ge=0)
    duration: int = Field(ge=1)
    velocity: int = Field(default=100, ge=0, le=127)
    pattern_id: Optional[UUID] = None
    channel_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Pattern(SQLModel, table=True):
    __tablename__ = "daw_pattern"
    __table_args__ = {"schema": "daw", "extend_existing": True}

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(default="Pattern 1")
    length: int = Field(default=16, ge=1)
    project_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Clip(SQLModel, table=True):
    __tablename__ = "daw_clip"
    __table_args__ = {"schema": "daw", "extend_existing": True}

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    pattern_id: Optional[UUID] = None
    channel_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    start: int = Field(ge=0)
    length: int = Field(ge=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Channel(SQLModel, table=True):
    __tablename__ = "daw_channel"
    __table_args__ = {"schema": "daw", "extend_existing": True}

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    name: str
    type: ChannelType = Field(default=ChannelType.DRUM)
    color: str = Field(default="#3b82f6")
    volume: float = Field(default=0.8, ge=0, le=1)
    pan: float = Field(default=0, ge=-1, le=1)
    mute: bool = Field(default=False)
    solo: bool = Field(default=False)
    steps: str = Field(default="[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]")
    project_id: Optional[UUID] = None
    order_index: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DAWProject(SQLModel, table=True):
    __tablename__ = "daw_project"
    __table_args__ = {"schema": "daw", "extend_existing": True}

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    name: str
    description: Optional[str] = None
    user_id: Optional[UUID] = None
    bpm: int = Field(default=128, ge=20, le=300)
    time_signature: str = Field(default="[4, 4]")
    master_volume: float = Field(default=0.8, ge=0, le=1)
    status: ProjectStatus = Field(default=ProjectStatus.DRAFT)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


def steps_from_string(steps_str: str) -> List[int]:
    import json

    return json.loads(steps_str)


def steps_to_string(steps: List[int]) -> str:
    import json

    return json.dumps(steps)


def time_signature_from_string(ts_str: str) -> tuple:
    import json

    return tuple(json.loads(ts_str))


def time_signature_to_string(ts: tuple) -> str:
    import json

    return json.dumps(list(ts))


__all__ = [
    "Project",
    "Channel",
    "Pattern",
    "Note",
    "Clip",
    "ProjectStatus",
    "ChannelType",
    "steps_from_string",
    "steps_to_string",
    "time_signature_from_string",
    "time_signature_to_string",
]
