import pytest
import asyncio
from sqlmodel import select
from fastapi.testclient import TestClient

from common_lib.modules.data_storage.database.connection import get_session, init_db
from common_lib.modules.workflows.service import WorkflowService
from common_lib.modules.workflows.standard.models.observability import WorkflowExecution
from common_lib.modules.project_management.projects.models import ProjectBlueprint
from common_lib.modules.project_management.issues.models import Issue
from common_lib.modules.integration.adapters.projects_adapter import get_project_model

Project = get_project_model()

@pytest.mark.asyncio
async def test_agentic_loop_self_learning_e2e():
    """
    Test workflow execution failure triggering the self-learning feedback loop
    and creating a ticket in ProjectOS.
    """
    init_db()
    svc = WorkflowService()
    
    # 1. Define a failing mock workflow
    workflow_id = "test_failing_agent_workflow"
    req_data = {
        "name": "Test Failing Workflow",
        "description": "Fails due to an unregistered tool to trigger self-learning ticket creation.",
        "category": "Vision",
        "engine": "vision",
        "nodes": [
            {
                "id": "unregistered_node",
                "type": "unregistered.missing_tool",
                "toolId": "unregistered.missing_tool",
                "properties": {"param": "value"},
                "initialX": 100,
                "initialY": 100
            }
        ],
        "edges": []
    }
    
    # Create the workflow
    created_wf = svc.create_workflow(**req_data)
    workflow_id = created_wf["id"]
    
    # 2. Run the workflow and await completion/failure
    inputs = {"prompt": "Find target report data"}
    
    # Resolve the generator and consume it
    stream = await svc.run_workflow_by_id(workflow_id, inputs)
    
    events = []
    async for event in stream:
        events.append(event)
    print("EMITTED EVENTS:", events)
        
    # Wait for background SQLAlchemy DB commits to finish
    await asyncio.sleep(0.5)
        
    # 3. Verify the execution trace in the DB
    with next(get_session()) as session:
        # Check executions table
        stmt = select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow_id)
        executions = session.exec(stmt).all()
        assert len(executions) > 0, "WorkflowExecution should be saved in the database."
        assert executions[0].status == "failed"
        
        # Verify self-learning ticket has been created in the database
        proj_stmt = select(Project).where(Project.slug == "ai-feature-discovery")
        projects = session.exec(proj_stmt).all()
        assert len(projects) > 0, "Self-learning project should be created."
        
        issue_stmt = select(Issue).where(Issue.project_id == str(projects[0].id))
        issues = session.exec(issue_stmt).all()
        assert len(issues) > 0, "An issue should be created in the PM module for the failure."
        assert "unregistered.missing_tool" in issues[0].description_text
        print(f"Verified: Issue {issues[0].key} was successfully logged.")
