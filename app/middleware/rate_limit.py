"""Global ingress rate limiting middleware — P1-3.

Implements a sliding-window rate limiter keyed by:
  - Authenticated tenant/subject (when available from request.state.authz)
  - Client IP address as a fallback for unauthenticated requests

Special limits apply to expensive/sensitive endpoint groups:
  - auth (login, register, forgot-password)
  - generation (vision, audio, agents/chat)
  - download (model downloads)
  - streaming

Configuration is read from environment variables so limits can be tuned
without code changes.  All limits are per-window, per-key.

Environment variables:
  RATE_LIMIT_DEFAULT_RPM          — default requests/minute (default: 120)
  RATE_LIMIT_AUTH_RPM             — auth endpoints (default: 10)
  RATE_LIMIT_GENERATION_RPM       — AI generation endpoints (default: 20)
  RATE_LIMIT_DOWNLOAD_RPM         — model download endpoints (default: 5)
  RATE_LIMIT_STREAMING_RPM        — streaming endpoints (default: 10)
  RATE_LIMIT_ENABLED              — set to "false" to disable (default: true)
"""

import os
import time
import logging
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_ENABLED: bool = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() != "false"
_DEFAULT_RPM: int = int(os.environ.get("RATE_LIMIT_DEFAULT_RPM", "120"))
_AUTH_RPM: int = int(os.environ.get("RATE_LIMIT_AUTH_RPM", "10"))
_GENERATION_RPM: int = int(os.environ.get("RATE_LIMIT_GENERATION_RPM", "20"))
_DOWNLOAD_RPM: int = int(os.environ.get("RATE_LIMIT_DOWNLOAD_RPM", "5"))
_STREAMING_RPM: int = int(os.environ.get("RATE_LIMIT_STREAMING_RPM", "10"))

# Window size in seconds (sliding window of 1 minute)
_WINDOW_SECONDS: int = 60


# ---------------------------------------------------------------------------
# Endpoint group classification
# ---------------------------------------------------------------------------

def _classify_path(path: str) -> Tuple[str, int]:
    """Return (group_name, requests_per_minute_limit) for the given path."""
    # Auth — low limit to throttle brute-force
    if any(
        path.startswith(p)
        for p in (
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/access-token",
        )
    ):
        return "auth", _AUTH_RPM

    # Streaming — SSE / WebSocket endpoints are long-lived; limit connections
    if any(
        seg in path
        for seg in ("/stream", "/run-stream", "/fleet/status/stream")
    ):
        return "streaming", _STREAMING_RPM

    # Model downloads — expensive, must not overwhelm the download queue
    if "/models/" in path and "/download" in path:
        return "download", _DOWNLOAD_RPM

    # AI generation — GPU-heavy endpoints
    if any(
        path.startswith(p)
        for p in (
            "/api/v1/vision/",
            "/api/v1/audio/",
            "/api/v1/agents/chat",
            "/api/v1/agents/run",
        )
    ):
        return "generation", _GENERATION_RPM

    return "default", _DEFAULT_RPM


# ---------------------------------------------------------------------------
# Sliding window counter (in-process, single-instance safe)
# ---------------------------------------------------------------------------

# {key: deque of timestamps}
_windows: Dict[str, Deque[float]] = defaultdict(deque)


def _check_and_record(key: str, limit: int) -> Tuple[bool, int]:
    """Sliding window check.

    Returns:
        (allowed: bool, retry_after_seconds: int)
    """
    now = time.monotonic()
    window_start = now - _WINDOW_SECONDS
    dq = _windows[key]

    # Evict timestamps outside the window
    while dq and dq[0] < window_start:
        dq.popleft()

    if len(dq) >= limit:
        # Oldest request in window tells us when the window next clears
        retry_after = int(dq[0] - window_start) + 1
        return False, retry_after

    dq.append(now)
    return True, 0


def _rate_limit_key(request: Request, group: str) -> str:
    """Build a rate-limit key partitioned by identity and endpoint group."""
    # Prefer authenticated identity from authz middleware
    authz = getattr(request.state, "authz", None)
    if authz and authz.subject_id and authz.subject_id != "anonymous":
        identity_part = f"subj:{authz.subject_id}"
        tenant_part = f"tenant:{authz.tenant_id}"
    else:
        # Fall back to forwarded IP or direct client
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        ip = forwarded_for.split(",")[0].strip() if forwarded_for else (
            request.client.host if request.client else "unknown"
        )
        identity_part = f"ip:{ip}"
        tenant_part = "tenant:anon"

    return f"rl:{group}:{tenant_part}:{identity_part}"


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window ingress rate limiter (P1-3).

    Applied globally.  Keyed by tenant+subject from the authz context
    (set by AuthzMiddleware which runs after this one in the stack).
    Falls back to client IP for unauthenticated paths.

    Returns HTTP 429 with Retry-After when the limit is exceeded.
    Adds X-RateLimit-Limit and X-RateLimit-Remaining headers on all responses.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        if not _ENABLED:
            return await call_next(request)

        # OPTIONS preflights are never rate-limited
        if request.method == "OPTIONS":
            return await call_next(request)

        group, limit = _classify_path(request.url.path)
        key = _rate_limit_key(request, group)

        allowed, retry_after = _check_and_record(key, limit)

        if not allowed:
            logger.warning(
                "Rate limit exceeded: group=%s key=%s path=%s",
                group,
                key,
                request.url.path,
            )
            return Response(
                content=f'{{"detail":"Rate limit exceeded. Retry after {retry_after}s."}}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Group": group,
                },
            )

        response = await call_next(request)

        # Annotate response with rate limit info
        dq = _windows.get(key, deque())
        remaining = max(0, limit - len(dq))
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Group"] = group

        return response


__all__ = ["RateLimitMiddleware"]
