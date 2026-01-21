from typing import Optional, List, Dict
from datetime import datetime
from sqlmodel import Field, Relationship, Column, JSON
from app.modules.common.models.index import BaseModel
from .workflow import Workflow

class ProjectModule(BaseModel, table=True):
    __tablename__ = "project_modules"
    
    # Core
    name: str = Field(index=True)
    key: str = Field(unique=True, index=True) # e.g. "auth-module"
    description: Optional[str] = None
    
    # Hierarchy
    project_id: int = Field(foreign_key="projects.id", index=True)
    project: "Project" = Relationship(back_populates="modules")
    
    # Content
    workflows: List["Workflow"] = Relationship(back_populates="module")
    
    # Configuration
    config: Dict = Field(default={}, sa_column=Column(JSON))
    
    # Status
    is_active: bool = Field(default=True)
    version: str = Field(default="1.0.0")
    
    # Meta
    metadata_json: Dict = Field(default={}, sa_column=Column(JSON))
