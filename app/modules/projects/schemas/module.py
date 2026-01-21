from typing import Optional, List
from app.modules.projects.models.project_module import ProjectModule
from app.modules.projects.schemas.workflow import WorkflowRead
from sqlmodel import SQLModel

class ProjectModuleBase(SQLModel):
    name: str
    key: str
    description: Optional[str] = None
    is_active: bool = True

class ProjectModuleRead(ProjectModuleBase):
    id: int
    project_id: int
    workflows: List[WorkflowRead] = []
