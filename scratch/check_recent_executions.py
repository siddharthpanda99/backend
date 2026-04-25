import os
import sys

# Add the Backend directory to sys.path
sys.path.append(os.getcwd())

from app.modules.database.service.connection import engine
from sqlmodel import Session, select, text
from app.modules.workflows.observability.models import WorkflowExecution

def check_recent_executions():
    with Session(engine) as session:
        try:
            # Set search path for PostgreSQL if applicable
            session.execute(text("SET search_path TO observability"))
        except:
            pass
            
        try:
            statement = select(WorkflowExecution).order_by(WorkflowExecution.started_at.desc()).limit(10)
            executions = session.exec(statement).all()
            
            print(f"Total Executions found: {len(executions)}")
            for e in executions:
                print(f"ID: {e.trace_id}")
                print(f"  Workflow: {e.workflow_name}")
                print(f"  Status: {e.status}")
                print(f"  Started At: {e.started_at}")
                print(f"  Completed At: {e.completed_at}")
                print("-" * 20)
        except Exception as ex:
            print(f"Error: {ex}")

if __name__ == "__main__":
    check_recent_executions()
