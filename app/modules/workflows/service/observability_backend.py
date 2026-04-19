from typing import Optional
from common_lib.modules.workflows.standard.observability.events import Event, EventType
from common_lib.modules.workflows.standard.observability.tracer import EventBackend
from app.modules.workflows.models.observability import WorkflowExecution, WorkflowEvent
from app.modules.database.service.connection import engine
from sqlmodel import Session, select
import json
import logging

logger = logging.getLogger(__name__)

class PostgresEventBackend(EventBackend):
    """
    Observability backend that persists workflow events and execution metadata
    to the central PostgreSQL database in the 'observability' schema.
    """
    def emit(self, event: Event) -> None:
        with Session(engine) as session:
            try:
                # 1. Handle Workflow Lifecycle Updates
                if event.event_type == EventType.WORKFLOW_STARTED:
                    execution = WorkflowExecution(
                        trace_id=event.trace_id,
                        workflow_id=event.workflow_id,
                        workflow_name=event.metadata.get("workflow_name"),
                        agent_id=event.metadata.get("agent_id"),
                        status="running",
                        started_at=event.timestamp,
                        inputs=event.metadata.get("initial_inputs", {})
                    )
                    session.merge(execution)
                
                elif event.event_type == EventType.WORKFLOW_COMPLETED:
                    execution = session.get(WorkflowExecution, event.trace_id)
                    if execution:
                        execution.status = "completed"
                        execution.completed_at = event.timestamp
                        execution.duration_ms = event.metadata.get("duration_ms")
                        execution.outputs = event.metadata.get("outputs", {})
                        session.add(execution)
                
                elif event.event_type == EventType.WORKFLOW_FAILED:
                    execution = session.get(WorkflowExecution, event.trace_id)
                    if execution:
                        execution.status = "failed"
                        execution.completed_at = event.timestamp
                        execution.error = event.metadata.get("error")
                        session.add(execution)

                # 2. Persist Granular Event/Span
                db_event = WorkflowEvent(
                    event_type=event.event_type.value,
                    timestamp=event.timestamp,
                    trace_id=event.trace_id,
                    span_id=event.span_id,
                    parent_span_id=event.parent_span_id,
                    workflow_id=event.workflow_id,
                    node_id=event.metadata.get("node_id"),
                    event_metadata=event.metadata
                )
                session.add(db_event)
                session.commit()
            except Exception as e:
                logger.error(f"Failed to persist observability event: {e}")
                session.rollback()

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass
