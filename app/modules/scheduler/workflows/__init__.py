"""Scheduler workflow executors.

Each module here exports an executor function that gets registered
with the workflow registry on import.
"""

from app.modules.scheduler.workflows import sd_news
from app.modules.scheduler.workflows import platform_workflows
from app.modules.scheduler.workflow_registry import register_workflow


def register_all_workflows():
    """Register all built-in workflow executors."""
    # SD News
    register_workflow("sd_news_reddit", sd_news.execute_sd_news_workflow)

    # Data Pipeline
    register_workflow("rag_pipeline", platform_workflows.execute_rag_pipeline)
    register_workflow("pii_compliance", platform_workflows.execute_pii_compliance)

    # Memory Maintenance
    register_workflow(
        "memory_security_audit", platform_workflows.execute_memory_security_audit
    )
    register_workflow(
        "memory_observability", platform_workflows.execute_memory_observability
    )
    register_workflow(
        "memory_economics_tracking", platform_workflows.execute_memory_economics
    )
    register_workflow(
        "memory_federation_sync", platform_workflows.execute_memory_federation_sync
    )
