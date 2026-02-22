from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

class ToolBase(BaseModel):
    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    tools_list: Optional[list] = []
    parent: Optional[str] = None

class ToolCreate(ToolBase):
    id: str

class ToolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tools_list: Optional[list] = None
    parent: Optional[str] = None

class ToolRead(ToolBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
