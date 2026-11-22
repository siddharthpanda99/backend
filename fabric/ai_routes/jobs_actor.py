"""Fabric-side actor plumbing for background jobs (shared, cross-module).

Port of ``Backend/app/modules/jobs/actor.py``. Job records carry ``user_id``
so job listings can be filtered per actor. The Backend version stashes the
authenticated subject id from ``app.modules.auth``; the fabric control
plane has no auth layer, so ``capture_job_actor`` is a no-op dependency
and the actor is left unset.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Optional

_actor: ContextVar[str] = ContextVar("job_actor", default="")


async def capture_job_actor() -> None:
    """No-op actor capture: the fabric control plane has no auth layer."""
    _actor.set("")


def current_actor() -> str:
    """Return the acting subject id for the current request ('' when unknown)."""
    return _actor.get()


class OwnedJobService:
    """``JobService`` proxy that stamps the current actor onto submits.

    Every other attribute is delegated, so callers keep using the plain
    service API (``get``/``list``/``cancel``/``register_executor``/…).
    """

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
    """Return the actor-aware jobs service proxy (no executor registration)."""
    from common_lib.modules.jobs.service import get_job_service

    return OwnedJobService(get_job_service())


__all__ = [
    "OwnedJobService",
    "capture_job_actor",
    "current_actor",
    "owned_job_service",
]
