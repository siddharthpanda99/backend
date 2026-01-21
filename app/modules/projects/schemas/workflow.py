from typing import Optional, List
from app.modules.projects.models.workflow import Workflow
from app.modules.projects.schemas.task import TaskRead
from sqlmodel import SQLModel

class WorkflowBase(SQLModel):
    name: str
    key: str
    description: Optional[str] = None
    is_active: bool = True

class WorkflowRead(WorkflowBase):
    id: int
    module_id: int
    tasks: List[TaskRead] = []
