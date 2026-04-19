# DAW Schemas - Pydantic models for DAW entities
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
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


# Base schemas
class DAWBase(BaseModel):
    name: str
    description: Optional[str] = None


# Project schemas
class DAWProjectCreate(DAWBase):
    bpm: int = Field(default=128, ge=20, le=300)
    time_signature: tuple = Field(default=(4, 4))
    master_volume: float = Field(default=0.8, ge=0, le=1)


class DAWProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    bpm: Optional[int] = None
    time_signature: Optional[tuple] = None
    master_volume: Optional[float] = None
    status: Optional[ProjectStatus] = None


class DAWProjectResponse(DAWBase):
    id: UUID
    user_id: UUID
    bpm: int
    time_signature: tuple
    master_volume: float
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    channels: List[str]  # Simplified
    patterns: List[str]  # Simplified
    clips: List[str]  # Simplified

    class Config:
        from_attributes = True


# Channel schemas
class ChannelCreate(BaseModel):
    name: str
    type: ChannelType
    color: str = "#3b82f6"
    volume: float = Field(default=0.8, ge=0, le=1)
    pan: float = Field(default=0, ge=-1, le=1)
    mute: bool = False
    solo: bool = False
    steps: List[int] = Field(default_factory=lambda: [0] * 16)


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    volume: Optional[float] = None
    pan: Optional[float] = None
    mute: Optional[bool] = None
    solo: Optional[bool] = None
    steps: Optional[List[int]] = None


class ChannelResponse(ChannelCreate):
    id: UUID
    project_id: UUID
    order_index: int
    created_at: datetime

    class Config:
        from_attributes = True


# Pattern schemas
class PatternCreate(BaseModel):
    name: str
    length: int = 16
    notes: List[Dict[str, Any]] = Field(default_factory=list)


class PatternUpdate(BaseModel):
    name: Optional[str] = None
    length: Optional[int] = None
    notes: Optional[List[Dict[str, Any]]] = None


class PatternResponse(PatternCreate):
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Note schemas
class NoteCreate(BaseModel):
    pitch: int = Field(ge=0, le=127)
    start: int = Field(ge=0)
    duration: int = Field(ge=1)
    velocity: int = Field(default=100, ge=0, le=127)
    channel_id: UUID


class NoteUpdate(BaseModel):
    pitch: Optional[int] = None
    start: Optional[int] = None
    duration: Optional[int] = None
    velocity: Optional[int] = None


class NoteResponse(NoteCreate):
    id: UUID
    pattern_id: UUID

    class Config:
        from_attributes = True


# Clip schemas
class ClipCreate(BaseModel):
    pattern_id: UUID
    channel_id: UUID
    start: int = Field(ge=0)
    length: int = Field(ge=1)


class ClipUpdate(BaseModel):
    pattern_id: Optional[UUID] = None
    channel_id: Optional[UUID] = None
    start: Optional[int] = None
    length: Optional[int] = None


class ClipResponse(ClipCreate):
    id: UUID
    project_id: UUID

    class Config:
        from_attributes = True


# Export format for frontend
class DAWExport(BaseModel):
    project: Dict[str, Any]
    channels: List[Dict[str, Any]]
    patterns: List[Dict[str, Any]]
    clips: List[Dict[str, Any]]
    version: str = "1.0.0"


__all__ = [
    "DAWProjectCreate",
    "DAWProjectUpdate",
    "DAWProjectResponse",
    "ChannelCreate",
    "ChannelUpdate",
    "ChannelResponse",
    "PatternCreate",
    "PatternUpdate",
    "PatternResponse",
    "NoteCreate",
    "NoteUpdate",
    "NoteResponse",
    "ClipCreate",
    "ClipUpdate",
    "ClipResponse",
    "DAWExport",
    "ProjectStatus",
    "ChannelType",
]
