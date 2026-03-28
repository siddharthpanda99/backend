from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

class MemoryBase(BaseModel):
    name: str
    type: str = "vector"
    version: str = "1.0.0"
    definition: Optional[dict] = None

class MemoryCreate(MemoryBase):
    id: str

class MemoryUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    definition: Optional[dict] = None

class MemoryRead(MemoryBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# --- TIERED MEMORY SCHEMAS ---

class SessionMemory(MemoryRead):
    conversation_id: str
    active_task: Optional[str] = None
    goals: Optional[list[str]] = []
    instructions: Optional[list[str]] = []
    constraints: Optional[list[str]] = []
    steps: Optional[list[dict[str, Any]]] = []
    node_state: Optional[dict[str, Any]] = {}
    metadata: Optional[dict[str, Any]] = {}

class LongTermMemory(MemoryRead):
    user_id: Optional[str] = "default"
    user_profile: Optional[dict[str, Any]] = {}
    preferences: Optional[list[str]] = []
    guardrails: Optional[list[str]] = []
    facts: Optional[list[dict[str, Any]]] = []
    behaviors: Optional[list[str]] = []
    summaries: Optional[list[str]] = []

class EpisodicMemory(MemoryRead):
    event_type: str
    event_payload: dict[str, Any]
    importance: float = 0.5
    timestamp: datetime
    conversation_id: Optional[str] = None
