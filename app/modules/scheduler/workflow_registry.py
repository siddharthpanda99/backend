"""Workflow Registry for Scheduler.

Maps workflow_id strings to actual executor functions.
New workflows register here to become available as cron job targets.
"""

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

WorkflowExecutor = Callable[[Dict[str, Any]], Any]

_registry: Dict[str, WorkflowExecutor] = {}


def register_workflow(workflow_id: str, executor: WorkflowExecutor):
    """Register a workflow executor function.

    Args:
        workflow_id: Unique identifier (matches UI workflow_id field).
        executor: Async function that takes workflow_inputs dict and returns result dict.
    """
    _registry[workflow_id] = executor
    logger.info(f"Registered workflow: {workflow_id}")


def get_workflow(workflow_id: str) -> Optional[WorkflowExecutor]:
    """Get a workflow executor by ID."""
    return _registry.get(workflow_id)


def list_workflows() -> Dict[str, str]:
    """List all registered workflows."""
    return {wid: str(exec) for wid, exec in _registry.items()}


async def execute_workflow(workflow_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a registered workflow.

    Args:
        workflow_id: The workflow to run.
        inputs: Configuration inputs from the cron job.

    Returns:
        Result dict from the workflow executor.

    Raises:
        ValueError: If workflow_id is not registered.
    """
    executor = _registry.get(workflow_id)
    if not executor:
        available = list(_registry.keys())
        raise ValueError(
            f"Workflow '{workflow_id}' not registered. Available: {available}"
        )

    return await executor(inputs)
