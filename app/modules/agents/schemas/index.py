from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

class AgentBase(BaseModel):
    name: str
    version: str = "1.0.0"
    description: Optional[dict] = None
    agent_type: Optional[str] = None
    identity: Optional[dict] = None
    definition: Optional[dict] = None
    is_active: bool = True

class AgentCreate(AgentBase):
    id: str

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[dict] = None
    definition: Optional[dict] = None
    is_active: Optional[bool] = None

class AgentRead(AgentBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
