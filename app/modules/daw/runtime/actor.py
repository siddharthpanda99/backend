"""Authenticated-actor plumbing for DAW background jobs.

DAW job records carry ``user_id`` so ``GET /api/v1/jobs?mine=true`` is
meaningful and cancellations can be attributed.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Annotated, Any, Optional

from fastapi import Depends

from common_lib.modules.auth.authorization import PlatformIdentity

from app.modules.auth.dependencies.authz import get_current_identity

_actor: ContextVar[str] = ContextVar("daw_job_actor", default="")


async def capture_job_actor(
    identity: Annotated[PlatformIdentity, Depends(get_current_identity)],
) -> None:
    """Stash the authenticated subject id for the current request."""
    _actor.set(str(identity.subject_id))


def current_actor() -> str:
    """Return the acting subject id for the current request ('' when unknown)."""
    return _actor.get()


class OwnedJobService:
    """``JobService`` proxy that stamps the current actor onto submits."""

    def __init__(self, service: Any) -> None:
        self._service = service

    def submit(
        self,
        kind: str,
        params: Optional[dict[str, Any]] = None,
        user_id: str = "",
        timeout: Optional[float] = None,
    ) -> Any:
        """Submit a job, defaulting ``user_id`` to the authenticated actor."""
        return self._service.submit(
            kind,
            params=params,
            user_id=user_id or current_actor(),
            timeout=timeout,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._service, name)


def owned_job_service() -> OwnedJobService:
    """Register DAW executors and return the actor-aware service proxy."""
    from app.modules.daw.runtime.job_executors import (
        ensure_daw_executors_registered,
    )
    from common_lib.modules.jobs.service import get_job_service

    ensure_daw_executors_registered()
    return OwnedJobService(get_job_service())


__all__ = [
    "OwnedJobService",
    "capture_job_actor",
    "current_actor",
    "owned_job_service",
]