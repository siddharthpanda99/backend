from typing import Optional
from sqlmodel import Field
from app.modules.common.models.index import BaseModel

class Permission(BaseModel, table=True):
    __tablename__ = "permissions"
    
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    
    resource: str = Field(index=True) # e.g. "users", "projects"
    action: str = Field(index=True)   # e.g. "read", "write"
