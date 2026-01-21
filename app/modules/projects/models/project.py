from typing import Optional, List, Dict
from datetime import datetime
from sqlmodel import Field, Column, JSON, Relationship
from app.modules.common.models.index import BaseModel
from .project_module import ProjectModule

class Project(BaseModel, table=True):
    __tablename__ = "projects"
    
    # Core Identity
    name: str = Field(index=True)
    slug: str = Field(unique=True, index=True)
    key: Optional[str] = Field(default=None, index=True, description="Short key e.g. PRJ")
    description: Optional[str] = None
    
    # Status & Accessibility
    is_public: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_archived: bool = Field(default=False)
    is_template: bool = Field(default=False)
    is_featured: bool = Field(default=False)
    
    # Workflow
    status: str = Field(default="planning", index=True)  # planning, active, on_hold, completed, cancelled
    priority: str = Field(default="medium", index=True)  # low, medium, high, critical
    
    # Timeline
    start_date: Optional[datetime] = None
    target_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    last_activity_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Categorization
    category: Optional[str] = Field(default=None, index=True)
    tags: List[str] = Field(default=[], sa_column=Column(JSON))
    
    # Commercial / Client
    client_name: Optional[str] = None
    budget: Optional[float] = None
    currency: str = Field(default="USD")
    
    # Resources & URLs
    website_url: Optional[str] = None
    repository_url: Optional[str] = None
    documentation_url: Optional[str] = None
    jira_url: Optional[str] = None
    slack_channel_id: Optional[str] = None
    
    # Media
    icon_url: Optional[str] = None
    banner_url: Optional[str] = None
    
    # Settings & Meta
    settings: Dict = Field(default={}, sa_column=Column(JSON))
    metadata_json: Dict = Field(default={}, sa_column=Column(JSON))
    
    # Structure
    modules: List["ProjectModule"] = Relationship(back_populates="project")

    # Ownership
    created_by_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_by: Optional["User"] = Relationship(back_populates="projects")
