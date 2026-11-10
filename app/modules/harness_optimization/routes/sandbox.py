"""Sandbox Routes.

Thin transport layer for sandbox execution.
"""

from typing import Optional, Dict
from fastapi import APIRouter, Depends, status

from common_lib.modules.harness_optimization.service import (
    get_harness_optimization_service,
)
from common_lib.modules.harness_optimization.flags import (
    is_hos_enabled,
    is_sandbox_enabled,
)
from common_lib.modules.harness_optimization.exceptions import FeatureDisabledError

from app.modules.harness_optimization.routes.schemas import (
    SandboxConfigSchema,
    SandboxRunRequest,
    SandboxRunResult,
    SandboxHealthCheck,
)

router = APIRouter(prefix="/sandbox", tags=["Sandbox"])


def _get_service():
    """Get HOS service instance."""
    if not is_hos_enabled() or not is_sandbox_enabled():
        raise FeatureDisabledError(
            "Sandbox feature is disabled",
            flag_name="HARNESS_OPT_SANDBOX_ENABLED",
        )
    return get_harness_optimization_service()


# Sandbox Execution


@router.post(
    "/run",
    response_model=SandboxRunResult,
    summary="Execute a command in a sandboxed container",
)
async def run_sandbox(payload: SandboxRunRequest, service=Depends(_get_service)):
    """Execute a command inside a sandboxed container with hardening options."""
    adapter = service.get_sandbox_adapter(payload.sandbox_config)
    result = await adapter.run(
        image=payload.image,
        command=payload.command,
        environment=payload.environment,
        volumes=payload.volumes,
    )
    return SandboxRunResult(**result)


@router.get(
    "/health",
    response_model=SandboxHealthCheck,
    summary="Sandbox health check",
)
async def sandbox_health(service=Depends(_get_service)):
    """Run a lightweight health check against the Docker daemon."""
    result = await service.sandbox_health_check()
    return SandboxHealthCheck(**result)


@router.get(
    "/monitor/{container_id}",
    response_model=dict,
    summary="Monitor container resources",
)
async def monitor_container(container_id: str, service=Depends(_get_service)):
    """Return current CPU / memory usage for a running container."""
    result = await service.monitor_sandbox_resources(container_id)
    return result


__all__ = ["router"]
