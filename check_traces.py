from app.modules.database.service.connection import engine
from sqlmodel import Session, select, text
from app.modules.workflows.observability.models import WorkflowExecution, WorkflowEvent
import json

def check_observability():
    with Session(engine) as session:
        try:
            # Check schema
            session.execute(text("SET search_path TO observability"))
            executions = session.exec(select(WorkflowExecution)).all()
            print(f"Total Executions: {len(executions)}")
            for e in executions:
                print(f"- {e.trace_id}: {e.status} ({e.workflow_name})")
            
            events = session.exec(select(WorkflowEvent)).all()
            print(f"Total Events: {len(events)}")
        except Exception as e:
            print(f"Error checking DB: {e}")

if __name__ == "__main__":
    check_observability()
