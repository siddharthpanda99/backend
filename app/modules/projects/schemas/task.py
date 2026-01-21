from typing import Optional, List, Dict
from app.modules.projects.models.task import Task
from sqlmodel import SQLModel

class TaskBase(SQLModel):
    name: str
    key: str
    description: Optional[str] = None
    type: str = "function"
    order_index: int = 0

class TaskRead(TaskBase):
    id: int
    workflow_id: int
