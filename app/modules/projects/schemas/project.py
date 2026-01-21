from typing import Optional, List, Dict
from datetime import datetime
from sqlmodel import SQLModel
from app.modules.projects.models.project import Project
from app.modules.projects.schemas.module import ProjectModuleRead

class ProjectBase(SQLModel):
    name: str
    key: Optional[str] = None
    slug: str
    description: Optional[str] = None
    status: str = "planning"
    priority: str = "medium"
    is_public: bool = False

from datetime import datetime
from pydantic import field_validator, model_validator
from app.modules.projects.models.project import Project

class ProjectCreate(ProjectBase):
    start_date: Optional[datetime] = None
    target_date: Optional[datetime] = None

    @model_validator(mode='after')
    def check_dates(self):
        if self.start_date and self.target_date:
            if self.target_date < self.start_date:
                raise ValueError('Target date must be after start date')
        return self

class ProjectUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None

class ProjectRead(ProjectBase):
    id: int
    created_by_id: Optional[int] = None
    modules: List[ProjectModuleRead] = []
