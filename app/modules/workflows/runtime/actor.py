"""Authenticated-actor plumbing for Workflow Failure Analysis background jobs."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Annotated, Any, Optional

from fastapi import Depends

from common_lib.modules.auth.authorization import PlatformIdentity

from app.modules.auth.dependencies.authz import get_current_identity

_actor: ContextVar[str] = ContextVar("workflow_fa_job_actor", default="")


async def capture_job_actor(
    identity: Annotated[PlatformIdentity, Depends(get_current_identity)],
) -> None:
    _actor.set(str(identity.subject_id))


def current_actor() -> str:
    return _actor.get()


class OwnedJobService:
    def __init__(self, service: Any) -> None:
        self._service = service

    def submit(
        self,
        kind: str,
        params: Optional[dict[str, Any]] = None,
        user_id: str = "",
        timeout: Optional[float] = None,
    ) -> Any:
        return self._service.submit(
            kind,
            params=params,
            user_id=user_id or current_actor(),
            timeout=timeout,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._service, name)


def owned_job_service() -> OwnedJobService:
    from app.modules.workflows.runtime.job_executors import (
        ensure_workflow_fa_executors_registered,
    )
    from common_lib.modules.jobs.service import get_job_service

    ensure_workflow_fa_executors_registered()
    return OwnedJobService(get_job_service())


__all__ = [
    "OwnedJobService",
    "capture_job_actor",
    "current_actor",
    "owned_job_service",
]