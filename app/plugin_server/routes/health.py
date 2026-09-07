"""Plugin Server routes — health, version, status."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def health_root(request: Request) -> dict[str, Any]:
    """Liveness check.

    Returns 200 if the server is up and the lifespan startup has
    completed. Use this for load-balancer health checks.
    """
    return {
        "status": "ok" if getattr(request.app.state, "ready", False) else "starting",
        "uptime_sec": (
            time.time() - request.app.state.started_at
            if getattr(request.app.state, "started_at", None)
            else 0
        ),
    }


@router.get("/version")
async def health_version() -> dict[str, Any]:
    """Server version and process info."""
    import platform as _platform
    import sys as _sys

    return {
        "service": "plugin-server",
        "version": "1.0.0",
        "python": _sys.version.split()[0],
        "platform": _platform.platform(),
        "pid": os.getpid(),
    }
