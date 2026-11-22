"""Worker client - execute a request on a worker via local loopback HTTP.

Acquires a worker from the supervisor (launching it if needed), POSTs the
WorkerRequest payload to the worker's /execute endpoint, then releases the
lease. The caller never needs to manage the worker lifecycle.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from fabric.supervisor import supervisor

logger = logging.getLogger(__name__)


class WorkerUnavailableError(RuntimeError):
    """Worker could not be acquired or become ready in time."""


async def execute_on_worker(
    profile_id: str,
    payload: Dict[str, Any],
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """POST `payload` to the worker registered for `profile_id`.

    Returns the worker's JSON response. Raises WorkerUnavailableError when the
    worker cannot be started. The worker's structured error body (if any) is
    returned as a dict with status="error" so callers can surface it.
    """
    worker = await supervisor.acquire_worker(profile_id)
    if worker is None:
        raise WorkerUnavailableError(f"failed to acquire worker for profile '{profile_id}'")

    url = f"http://127.0.0.1:{worker.port}/execute"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as e:
        logger.error("worker %s execute call failed: %s", profile_id, e)
        await supervisor.release_worker(profile_id)
        raise WorkerUnavailableError(f"worker '{profile_id}' request failed: {e}") from e

    worker.total_jobs += 1
    try:
        body = response.json()
    except Exception:
        body = {
            "status": "error",
            "error": f"worker returned HTTP {response.status_code} with non-JSON body",
        }

    await supervisor.release_worker(profile_id)
    return body


def worker_health(profile_id: str) -> Optional[Dict[str, Any]]:
    """Return the supervisor's info dict for the worker, or None."""
    return supervisor.get_worker_info(profile_id)
