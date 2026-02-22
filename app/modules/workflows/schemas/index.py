from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

class WorkflowBase(BaseModel):
    name: str
    version: str = "1.0.0"
    definition: Optional[dict] = None

class WorkflowCreate(WorkflowBase):
    id: str

class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    definition: Optional[dict] = None

class WorkflowRead(WorkflowBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
