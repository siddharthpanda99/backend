from sqlmodel import SQLModel, Field, Column, JSON, String, DateTime
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


class WorkflowExecution(SQLModel, table=True):
    __tablename__ = "workflow_executions"
    __table_args__ = {"schema": "observability", "extend_existing": True}

    trace_id: str = Field(primary_key=True)
    workflow_id: str = Field(index=True)
    workflow_name: Optional[str] = None
    agent_id: Optional[str] = None
    status: str = Field(default="running", index=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    outputs: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    # Combined state of all nodes for compliance audit
    state_snapshot: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class WorkflowEvent(SQLModel, table=True):
    __tablename__ = "workflow_events"
    __table_args__ = {"schema": "observability", "extend_existing": True}

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    event_type: str = Field(index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    trace_id: str = Field(index=True)
    span_id: str = Field(index=True)
    parent_span_id: Optional[str] = None
    workflow_id: str = Field(index=True)
    node_id: Optional[str] = Field(index=True)

    # Granular fields for compliance and analytics
    node_config: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    node_output: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    event_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
