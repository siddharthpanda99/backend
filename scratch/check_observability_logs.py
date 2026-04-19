import os
import sys

# Ensure the app context is loaded
sys.path.append(os.getcwd())

from sqlmodel import Session, select, text
from app.modules.database.service.connection import engine
from app.modules.workflows.models.observability import WorkflowExecution, WorkflowEvent

def check_logs():
    print("Checking Workflow Observability Logs...\n")
    
    with Session(engine) as session:
        # Check Executions
        print("--- Latest 5 Workflow Executions ---")
        stmt_exec = select(WorkflowExecution).order_by(WorkflowExecution.started_at.desc()).limit(5)
        executions = session.exec(stmt_exec).all()
        
        if not executions:
            print("No executions found in 'observability.workflow_executions'.")
        for ex in executions:
            print(f"ID: {ex.trace_id} | Workflow: {ex.workflow_id} | Status: {ex.status} | Started: {ex.started_at}")

        print("\n--- Latest 10 Workflow Events ---")
        # SQLModel might have issues with schemas in some versions, using text for safety if needed
        # but let's try the model first.
        stmt_event = select(WorkflowEvent).order_by(WorkflowEvent.timestamp.desc()).limit(10)
        events = session.exec(stmt_event).all()
        
        if not events:
            print("No events found in 'observability.workflow_events'.")
        for ev in events:
            print(f"Time: {ev.timestamp} | Type: {ev.event_type} | Trace: {ev.trace_id} | Node: {ev.node_id}")

if __name__ == "__main__":
    check_logs()
