from typing import Optional, List, Dict
from enum import Enum
from sqlmodel import Field, Relationship, Column, JSON
from app.modules.common.models.index import BaseModel

class TaskType(str, Enum):
    FUNCTION = "function"
    TOOL = "tool"
    API_CALL = "api_call"
    MANUAL_APPROVAL = "manual_approval"

class Task(BaseModel, table=True):
    __tablename__ = "tasks"
    
    # Core
    name: str = Field(index=True)
    key: str = Field(index=True) # key within workflow
    description: Optional[str] = None
    
    # Hierarchy
    workflow_id: int = Field(foreign_key="workflows.id", index=True)
    workflow: "Workflow" = Relationship(back_populates="tasks")
    
    # Execution Logic
    type: TaskType = Field(default=TaskType.FUNCTION, index=True)
    
    # Definition (The "What")
    function_name: Optional[str] = None # For internal functions
    tool_name: Optional[str] = None # For tools
    
    # Configuration (The "How")
    input_schema: Dict = Field(default={}, sa_column=Column(JSON)) # Expected inputs
    arguments: Dict = Field(default={}, sa_column=Column(JSON)) # Static args or template mapping
    
    # Behaviors
    is_async: bool = Field(default=False)
    timeout_seconds: int = Field(default=60)
    retry_count: int = Field(default=0)
    retry_delay_seconds: int = Field(default=5)
    
    # Sequencing
    order_index: int = Field(default=0, index=True)
    dependencies: List[str] = Field(default=[], sa_column=Column(JSON)) # List of task keys this depends on
    
    # Meta
    metadata_json: Dict = Field(default={}, sa_column=Column(JSON))
