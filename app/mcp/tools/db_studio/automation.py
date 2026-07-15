"""MCP tools for Scheduler, Jobs & Automation (UDS Module 22)."""

from typing import Optional

from common_lib.modules.db_studio.automation import (
    AutomationService,
    ScheduledJobCreate, ScheduledJobUpdate,
    WorkflowDefinitionCreate, WorkflowRunCreate,
    TriggerCreate, TriggerUpdate,
    QueueCreate,
)

svc = AutomationService()


def mcp_job_create(name: str, job_type: str = "sql", schedule_type: str = "cron",
                    cron_expression: str = None, max_retries: int = 3,
                    workspace_id: str = None) -> dict:
    """Create a scheduled job."""
    req = ScheduledJobCreate(
        name=name, job_type=job_type, schedule_type=schedule_type,
        cron_expression=cron_expression, max_retries=max_retries,
        workspace_id=workspace_id,
    )
    result = svc.create_job(req)
    return result.model_dump()


def mcp_job_list(job_type: str = None, workspace_id: str = None, limit: int = 50) -> list:
    """List scheduled jobs."""
    results = svc.list_jobs(job_type, workspace_id=workspace_id, limit=limit)
    return [r.model_dump() for r in results]


def mcp_job_get(job_id: str) -> Optional[dict]:
    """Get a scheduled job by ID."""
    result = svc.get_job(job_id)
    return result.model_dump() if result else None


def mcp_job_pause(job_id: str) -> Optional[dict]:
    """Pause a job."""
    result = svc.pause_job(job_id)
    return result.model_dump() if result else None


def mcp_job_resume(job_id: str) -> Optional[dict]:
    """Resume a job."""
    result = svc.resume_job(job_id)
    return result.model_dump() if result else None


def mcp_job_run(job_id: str, trigger_type: str = "manual") -> dict:
    """Execute a job (simulated)."""
    result = svc.run_job(job_id, trigger_type)
    return result.model_dump()


def mcp_job_runs_list(job_id: str = None, status: str = None, limit: int = 50) -> list:
    """List job runs."""
    results = svc.list_job_runs(job_id, status, limit)
    return [r.model_dump() for r in results]


def mcp_workflow_create(name: str, description: str = None, steps: list = None,
                         workspace_id: str = None) -> dict:
    """Create a workflow definition."""
    req = WorkflowDefinitionCreate(
        name=name, description=description, steps=steps, workspace_id=workspace_id,
    )
    result = svc.create_workflow(req)
    return result.model_dump()


def mcp_workflow_list(workspace_id: str = None, limit: int = 50) -> list:
    """List workflow definitions."""
    results = svc.list_workflows(workspace_id, limit)
    return [r.model_dump() for r in results]


def mcp_workflow_run(workflow_id: str, trigger_type: str = "manual") -> dict:
    """Execute a workflow (simulated)."""
    req = WorkflowRunCreate(trigger_type=trigger_type)
    result = svc.run_workflow(workflow_id, req)
    return result.model_dump()


def mcp_trigger_create(name: str, trigger_type: str, action_type: str = "run_job",
                        action_target_id: str = None, workspace_id: str = None) -> dict:
    """Create a trigger."""
    req = TriggerCreate(
        name=name, trigger_type=trigger_type, action_type=action_type,
        action_target_id=action_target_id, workspace_id=workspace_id,
    )
    result = svc.create_trigger(req)
    return result.model_dump()


def mcp_trigger_list(trigger_type: str = None, workspace_id: str = None,
                      limit: int = 50) -> list:
    """List triggers."""
    results = svc.list_triggers(trigger_type, workspace_id, limit)
    return [r.model_dump() for r in results]


def mcp_queue_create(name: str, queue_type: str = "fifo", priority: int = 0,
                      workspace_id: str = None) -> dict:
    """Create a queue."""
    req = QueueCreate(name=name, queue_type=queue_type, priority=priority,
                       workspace_id=workspace_id)
    result = svc.create_queue(req)
    return result.model_dump()


def mcp_retries_list(job_id: str = None, status: str = None, limit: int = 50) -> list:
    """List retry history."""
    results = svc.list_retries(job_id, status, limit)
    return [r.model_dump() for r in results]


def mcp_automation_dashboard() -> dict:
    """Get automation dashboard summary."""
    result = svc.get_dashboard()
    return result.model_dump()


def register_automation_tools(mcp_server):
    """Register all automation tools with the MCP server."""
    for name, fn in TOOLS.items():
        mcp_server.tool(name=name)(fn)
    return mcp_server


TOOLS = {
    "job_create": mcp_job_create,
    "job_list": mcp_job_list,
    "job_get": mcp_job_get,
    "job_pause": mcp_job_pause,
    "job_resume": mcp_job_resume,
    "job_run": mcp_job_run,
    "job_runs_list": mcp_job_runs_list,
    "workflow_create": mcp_workflow_create,
    "workflow_list": mcp_workflow_list,
    "workflow_run": mcp_workflow_run,
    "trigger_create": mcp_trigger_create,
    "trigger_list": mcp_trigger_list,
    "queue_create": mcp_queue_create,
    "retries_list": mcp_retries_list,
    "automation_dashboard": mcp_automation_dashboard,
}
