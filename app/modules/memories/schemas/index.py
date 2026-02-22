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
