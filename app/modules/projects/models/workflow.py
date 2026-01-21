from typing import Optional, List, Dict
from datetime import datetime
from sqlmodel import Field, Relationship, Column, JSON
from app.modules.common.models.index import BaseModel
from .task import Task

class Workflow(BaseModel, table=True):
    __tablename__ = "workflows"
    
    # Core
    name: str = Field(index=True)
    key: str = Field(unique=True, index=True) # e.g. "onboarding-flow"
    description: Optional[str] = None
    
    # Hierarchy
    module_id: int = Field(foreign_key="project_modules.id", index=True)
    module: "ProjectModule" = Relationship(back_populates="workflows")
    
    # Structure
    tasks: List["Task"] = Relationship(back_populates="workflow")
    
    # Execution Config
    is_sequential: bool = Field(default=True) # Run tasks one by one or parallel
    auto_trigger: bool = Field(default=False)
    trigger_events: List[str] = Field(default=[], sa_column=Column(JSON)) # e.g. ["user_signup", "daily_cron"]
    
    # Status
    is_active: bool = Field(default=True)
    
    # Meta
    variables: Dict = Field(default={}, sa_column=Column(JSON)) # Global variables for the workflow
    metadata_json: Dict = Field(default={}, sa_column=Column(JSON))
