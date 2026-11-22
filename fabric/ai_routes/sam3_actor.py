"""Fabric-side actor plumbing for SAM3 background jobs.

Port of ``Backend/app/modules/sam3/runtime/actor.py``. The Backend version
stashes the authenticated subject id from ``app.modules.auth``; the fabric
control plane has no auth layer, so ``capture_job_actor`` is a no-op
dependency that leaves the actor unset.

The SAM3 job-kind constants live here because the Backend defines them in
``app/modules/sam3/runtime/job_executors.py`` (fabric-side copies of the
executors are a follow-up).
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Optional

_actor: ContextVar[str] = ContextVar("sam3_job_actor", default="")


async def capture_job_actor() -> None:
    """No-op actor capture: the fabric control plane has no auth layer."""
    _actor.set("")


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
        """Submit a job, defaulting ``user_id`` to the acting actor."""
        return self._service.submit(
            kind,
            params=params,
            user_id=user_id or current_actor(),
            timeout=timeout,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._service, name)


def owned_job_service() -> OwnedJobService:
    """Return the actor-aware job-service proxy.

    Backend version also registers the SAM3 job executors
    (``ensure_sam3_executors_registered``); executor registration is
    Backend-app-side for now, so the fabric returns the proxy over the
    common_lib job service directly.
    """
    from common_lib.modules.jobs.service import get_job_service

    return OwnedJobService(get_job_service())


# Job kinds (ported from app/modules/sam3/runtime/job_executors.py).
SESSION_ACTION_KIND = "sam3.session_action"
SESSION_ACTION_DEVICE = "gpu"
SESSION_ACTION_TIMEOUT = 300.0
SESSION_CREATE_KIND = "sam3.session_create"
SESSION_CREATE_DEVICE = "gpu"
SESSION_CREATE_TIMEOUT = 120.0

__all__ = [
    "OwnedJobService",
    "SESSION_ACTION_KIND",
    "SESSION_CREATE_KIND",
    "capture_job_actor",
    "current_actor",
    "owned_job_service",
]
