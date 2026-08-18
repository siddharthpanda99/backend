"""Response Caching Middleware — centralized HTTP response cache.

Integrates with the integration module for event routing, error handling,
and trace context propagation. Feature-flagged via RESPONSE_CACHE_ENABLED.
"""

import time
import hashlib
import json
import logging
from typing import Optional, Dict, Any, Set
from collections import OrderedDict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from cachetools import TTLCache

from common_lib.modules.integration import (
    get_event_router,
    get_error_handler,
    ErrorSeverity,
)
from common_lib.modules.integration.core.context_propagation import create_trace_context

logger = logging.getLogger(__name__)

STREAMING_PATHS: Set[str] = {
    "/stream",
    "/run-stream",
    "/fleet/status/stream",
    "/tasks",
}
# P0-2 FIX: Exclusions now use full /api/v1/* prefixes so they actually match.
# Previously "/auth" failed to match "/api/v1/auth/login".
EXCLUDED_PREFIXES: Set[str] = {
    "/api/v1/auth",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/entities/registry",
    "/api/v1/memories",
    "/api/v1/agents",
}
CACHEABLE_METHODS: Set[str] = {"GET", "HEAD"}
# P0-2 FIX: Disabled by default. Enable explicitly via RESPONSE_CACHE_ENABLED=true env var
# ONLY after identity-aware cache isolation has been verified with integration tests.
RESPONSE_CACHE_ENABLED: bool = False


class _SizeAwareTTLCache(TTLCache):
    """TTLCache that tracks total stored size for stats."""

    def __init__(self, maxsize: int, ttl: float, **kwargs):
        super().__init__(maxsize, ttl, **kwargs)
        self.total_size_bytes: int = 0
        self.hits: int = 0
        self.misses: int = 0

    def __getitem__(self, key):
        val = super().__getitem__(key)
        self.hits += 1
        return val

    def __missing__(self, key):
        self.misses += 1
        raise KeyError(key)

    def __setitem__(self, key, value):
        old_val = self.pop(key, None)
        if old_val is not None:
            self.total_size_bytes -= len(old_val.get("body", b""))
        super().__setitem__(key, value)
        self.total_size_bytes += len(value.get("body", b""))

    def popitem(self):
        key, val = super().popitem()
        self.total_size_bytes -= len(val.get("body", b""))
        return key, val


_cache: Optional[_SizeAwareTTLCache] = None


def _get_cache() -> _SizeAwareTTLCache:
    global _cache
    if _cache is None:
        _cache = _SizeAwareTTLCache(maxsize=512, ttl=300)
    return _cache


def _cache_key(request: Request) -> str:
    """Build a cache key that includes tenant and auth identity partitions.

    P0-2 FIX: Previously only method+path+query were hashed, making it
    possible for user-A's response to be served to user-B.  Now we hash:
    - HTTP method, path, query string  (request identity)
    - Hashed Authorization header      (user/session partition)
    - X-Tenant-Id header               (tenant partition)
    - Accept header                    (representation partition)
    """
    auth_raw = request.headers.get("authorization", "")
    # Hash the token so we don't store credentials in the cache key.
    auth_hash = hashlib.sha256(auth_raw.encode()).hexdigest()[:16]
    tenant = request.headers.get("x-tenant-id", "default")
    accept = request.headers.get("accept", "*/*")
    raw = f"{request.method}:{request.url.path}:{request.url.query}:{auth_hash}:{tenant}:{accept}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _should_cache(request: Request) -> bool:
    if not RESPONSE_CACHE_ENABLED:
        return False
    if request.method not in CACHEABLE_METHODS:
        return False
    path = request.url.path
    for prefix in EXCLUDED_PREFIXES:
        if path.startswith(prefix):
            return False
    for sp in STREAMING_PATHS:
        if sp in path:
            return False
    cache_control = request.headers.get("cache-control", "")
    if "no-cache" in cache_control or "no-store" in cache_control:
        return False
    return True


def _is_response_cacheable(response: Response) -> bool:
    """P0-2 FIX: Only cache safe, non-sensitive 2xx responses.

    Rules:
    - Only 200 and 206 are cached (not 4xx/5xx).
    - Responses carrying Set-Cookie are never stored (session / auth cookies).
    - Responses with Cache-Control: private or no-store are excluded.
    """
    if response.status_code not in (200, 206):
        return False
    if "set-cookie" in response.headers:
        return False
    cc = response.headers.get("cache-control", "")
    if "private" in cc or "no-store" in cc:
        return False
    return True


class ResponseCacheMiddleware(BaseHTTPMiddleware):
    """Middleware that caches HTTP responses with integration module hooks."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._event_router = get_event_router()
        self._error_handler = get_error_handler()

    async def dispatch(self, request: Request, call_next) -> Response:
        if not _should_cache(request):
            return await call_next(request)

        key = _cache_key(request)
        cache = _get_cache()

        try:
            cached = cache.get(key)
            if cached is not None:
                response = Response(
                    content=cached["body"],
                    status_code=cached["status_code"],
                    headers=cached["headers"],
                    media_type=cached.get("media_type"),
                )
                response.headers["X-Cache"] = "HIT"
                return response
        except Exception as e:
            self._error_handler.handle_error(
                error=e,
                module="response_cache",
                operation="read",
                severity=ErrorSeverity.WARNING,
            )

        response = await call_next(request)

        if _is_response_cacheable(response):
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            cache_entry = {
                "body": body,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type,
                "cached_at": time.time(),
            }
            cache[key] = cache_entry

            response = Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
            response.headers["X-Cache"] = "MISS"
        else:
            # Drain the body so the connection is properly closed even when we skip caching.
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            response = Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response


def get_cache_stats() -> Dict[str, Any]:
    """Get response cache statistics."""
    cache = _get_cache()
    return {
        "enabled": RESPONSE_CACHE_ENABLED,
        "size": len(cache),
        "maxsize": cache.maxsize,
        "ttl": cache.ttl,
        "total_size_bytes": cache.total_size_bytes,
        "hits": cache.hits,
        "misses": cache.misses,
        "hit_rate": round(cache.hits / (cache.hits + cache.misses + 1) * 100, 1),
        "currsize": len(cache),
    }


def clear_response_cache() -> bool:
    """Clear the entire response cache."""
    global _cache
    _cache = None
    return True


__all__ = [
    "ResponseCacheMiddleware",
    "get_cache_stats",
    "clear_response_cache",
    "RESPONSE_CACHE_ENABLED",
]
