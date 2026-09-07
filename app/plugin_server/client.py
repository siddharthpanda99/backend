"""PluginServerClient — HTTP client for the separate Plugin Server.

The main backend (port 8000) uses this class to talk to the
Plugin Server (port 8081). The class:

  - Caches the plugin list with a TTL
  - Translates HTTP errors to typed exceptions
  - Tracks circuit-breaker state: if the server fails N times in
    a row, stop calling it for a cooldown period
  - Falls back to a local in-process PluginManager if the server
    is unreachable AND PLUGIN_SERVER_ENABLED=0 (legacy mode)

This is the ONLY place in the main backend that knows about
HTTP. Every plugin-related call goes through here.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# Exceptions
class PluginServerError(Exception):
    """Base error from the Plugin Server."""


class PluginServerUnreachable(PluginServerError):
    """The Plugin Server is not reachable (network/timeout)."""


class PluginServerCircuitOpen(PluginServerError):
    """The circuit breaker is open; the Plugin Server is being given
    a cooldown after too many failures."""


class PluginServerToolError(PluginServerError):
    """The Plugin Server returned an error for a tool call."""

    def __init__(self, message: str, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class PluginServerClient:
    """HTTP client for the Plugin Server.

    Usage::

        client = PluginServerClient(
            base_url="http://localhost:8081",
            timeout_sec=60.0,
        )

        plugins = client.list_plugins()  # List[dict]
        result = client.execute_tool(
            "github", "create_issue", {"title": "...", "body": "..."}
        )  # returns dict from the server

    Caching:
        - list_plugins() result is cached for ``cache_ttl_sec``
          (default 30s). Call invalidate_cache() after a reload
          if you need fresh data immediately.
        - Tool calls are NOT cached.

    Circuit breaker:
        - If ``failure_threshold`` consecutive requests fail, the
          circuit opens and subsequent calls raise
          ``PluginServerCircuitOpen`` for ``circuit_cooldown_sec``.
        - The circuit resets after a successful request.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout_sec: float = 60.0,
        health_timeout_sec: float = 2.0,
        cache_ttl_sec: float = 30.0,
        failure_threshold: int = 3,
        circuit_cooldown_sec: float = 60.0,
    ):
        self.base_url = (
            base_url or os.environ.get("PLUGIN_SERVER_URL", "http://localhost:8081")
        ).rstrip("/")
        self.timeout_sec = timeout_sec
        self.health_timeout_sec = health_timeout_sec
        self.cache_ttl_sec = cache_ttl_sec
        self.failure_threshold = failure_threshold
        self.circuit_cooldown_sec = circuit_cooldown_sec

        # Threading primitives for the circuit breaker
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._circuit_opened_at: float | None = None

        # Plugin list cache
        self._cache_lock = threading.Lock()
        self._cache: list[dict] | None = None
        self._cache_at: float = 0.0

        # Single shared client (lazy)
        self._client: httpx.Client | None = None
        # For async usage
        self._async_client: httpx.AsyncClient | None = None

    # ── Lifecycle ────────────────────────────────────────────────

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout_sec,
            )
        return self._client

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_sec,
            )
        return self._async_client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        if self._async_client is not None:
            # Async client close is async, so do it synchronously
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._async_client.aclose())
                else:
                    loop.run_until_complete(self._async_client.aclose())
            except Exception:
                pass

    # ── Circuit breaker ──────────────────────────────────────────

    def _check_circuit(self) -> None:
        with self._lock:
            if self._circuit_opened_at is not None:
                elapsed = time.time() - self._circuit_opened_at
                if elapsed < self.circuit_cooldown_sec:
                    raise PluginServerCircuitOpen(
                        f"Plugin Server circuit breaker is open "
                        f"({elapsed:.0f}s of {self.circuit_cooldown_sec}s cooldown)"
                    )
                # Cooldown expired; reset
                self._circuit_opened_at = None
                self._consecutive_failures = 0

    def _record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._circuit_opened_at = None

    def _record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.failure_threshold:
                if self._circuit_opened_at is None:
                    self._circuit_opened_at = time.time()
                    logger.warning(
                        f"PluginServerClient: circuit breaker OPENED after "
                        f"{self._consecutive_failures} consecutive failures"
                    )

    # ── High-level API ────────────────────────────────────────────

    def health(self) -> bool:
        """Check if the Plugin Server is alive."""
        self._check_circuit()
        try:
            r = self._get_client().get("/health", timeout=self.health_timeout_sec)
            if r.status_code == 200:
                self._record_success()
                return True
            return False
        except (httpx.HTTPError, OSError) as e:
            self._record_failure()
            logger.debug(f"Plugin server health check failed: {e}")
            return False

    def list_plugins(self, *, use_cache: bool = True, **filters: Any) -> list[dict]:
        """List loaded tool plugins. Cached for cache_ttl_sec."""
        with self._cache_lock:
            now = time.time()
            if (
                use_cache
                and self._cache is not None
                and now - self._cache_at < self.cache_ttl_sec
            ):
                return self._cache

        self._check_circuit()
        try:
            r = self._get_client().get("/plugins", params=filters or None, timeout=10.0)
            r.raise_for_status()
            data = r.json()
            plugins = data.get("plugins", [])
        except (httpx.HTTPError, OSError) as e:
            self._record_failure()
            raise PluginServerUnreachable(f"list_plugins failed: {e}") from e

        self._record_success()
        with self._cache_lock:
            self._cache = plugins
            self._cache_at = time.time()
        return plugins

    def invalidate_cache(self) -> None:
        with self._cache_lock:
            self._cache = None
            self._cache_at = 0.0

    def get_plugin(self, plugin_id: str) -> dict:
        """Get one tool plugin's metadata."""
        self._check_circuit()
        try:
            r = self._get_client().get(f"/plugins/{plugin_id}", timeout=10.0)
            if r.status_code == 404:
                raise PluginServerError(f"Plugin '{plugin_id}' not found")
            r.raise_for_status()
            self._record_success()
            return r.json()
        except (httpx.HTTPError, OSError) as e:
            self._record_failure()
            raise PluginServerUnreachable(f"get_plugin failed: {e}") from e

    def safe_reload_plugin(self, plugin_id: str) -> dict:
        """Safe-reload a single tool plugin."""
        self._check_circuit()
        self.invalidate_cache()  # cache is stale after reload
        try:
            r = self._get_client().post(
                f"/plugins/{plugin_id}/safe-reload", timeout=120.0
            )
            if r.status_code == 404:
                raise PluginServerError(f"Plugin '{plugin_id}' not found")
            if r.status_code == 503:
                raise PluginServerError(f"Plugin is already reloading: {r.text}")
            r.raise_for_status()
            self._record_success()
            return r.json()
        except (httpx.HTTPError, OSError) as e:
            self._record_failure()
            raise PluginServerUnreachable(f"safe_reload_plugin failed: {e}") from e

    def reload_all(self) -> dict:
        """Reload all tool plugins (naive)."""
        self._check_circuit()
        self.invalidate_cache()
        try:
            r = self._get_client().post("/plugins/reload", timeout=120.0)
            r.raise_for_status()
            self._record_success()
            return r.json()
        except (httpx.HTTPError, OSError) as e:
            self._record_failure()
            raise PluginServerUnreachable(f"reload_all failed: {e}") from e

    def execute_tool(
        self,
        plugin_id: str,
        tool_name: str,
        params: dict,
        *,
        timeout_sec: float | None = None,
    ) -> dict:
        """Execute a tool. Returns the server's response dict.

        Raises:
            PluginServerUnreachable: server is down / unreachable
            PluginServerToolError: tool execution failed
            PluginServerCircuitOpen: circuit breaker is open
        """
        self._check_circuit()
        body = {
            "plugin_id": plugin_id,
            "tool_name": tool_name,
            "params": params,
        }
        if timeout_sec is not None:
            body["timeout_sec"] = timeout_sec

        try:
            r = self._get_client().post(
                "/tools/execute", json=body, timeout=self.timeout_sec
            )
        except (httpx.HTTPError, OSError) as e:
            self._record_failure()
            raise PluginServerUnreachable(f"execute_tool failed: {e}") from e

        if r.status_code == 503:
            # Plugin is reloading — propagate the detail
            self._record_failure()  # counts as a failure too
            try:
                detail = r.json()
            except Exception:
                detail = {"error": r.text}
            raise PluginServerToolError(
                f"tool unavailable: {detail.get('error', 'reloading')}",
                status_code=503,
                body=detail,
            )
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = {"error": r.text}
            self._record_success()  # server answered, just an error
            raise PluginServerToolError(
                f"tool failed: {detail.get('error', r.text)}",
                status_code=r.status_code,
                body=detail,
            )
        self._record_success()
        return r.json()

    async def execute_tool_async(
        self,
        plugin_id: str,
        tool_name: str,
        params: dict,
        *,
        timeout_sec: float | None = None,
    ) -> dict:
        """Async version of execute_tool."""
        self._check_circuit()
        body = {
            "plugin_id": plugin_id,
            "tool_name": tool_name,
            "params": params,
        }
        if timeout_sec is not None:
            body["timeout_sec"] = timeout_sec

        try:
            r = await self._get_async_client().post("/tools/execute", json=body)
        except (httpx.HTTPError, OSError) as e:
            self._record_failure()
            raise PluginServerUnreachable(f"execute_tool failed: {e}") from e

        if r.status_code == 503:
            try:
                detail = r.json()
            except Exception:
                detail = {"error": r.text}
            self._record_failure()
            raise PluginServerToolError(
                f"tool unavailable: {detail.get('error', 'reloading')}",
                status_code=503,
                body=detail,
            )
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = {"error": r.text}
            self._record_success()
            raise PluginServerToolError(
                f"tool failed: {detail.get('error', r.text)}",
                status_code=r.status_code,
                body=detail,
            )
        self._record_success()
        return r.json()

    # ── Convenience: list / extensions / infra ──────────────────

    def list_extensions(self) -> list[dict]:
        self._check_circuit()
        try:
            r = self._get_client().get("/extensions", timeout=10.0)
            r.raise_for_status()
            self._record_success()
            return r.json().get("extensions", [])
        except (httpx.HTTPError, OSError) as e:
            self._record_failure()
            raise PluginServerUnreachable(f"list_extensions failed: {e}") from e

    def list_infra_plugins(self) -> list[dict]:
        self._check_circuit()
        try:
            r = self._get_client().get("/infra/plugins", timeout=10.0)
            r.raise_for_status()
            self._record_success()
            return r.json().get("plugins", [])
        except (httpx.HTTPError, OSError) as e:
            self._record_failure()
            raise PluginServerUnreachable(f"list_infra_plugins failed: {e}") from e

    def list_services(self) -> list[str]:
        self._check_circuit()
        try:
            r = self._get_client().get("/infra/services", timeout=10.0)
            r.raise_for_status()
            self._record_success()
            return r.json().get("services", [])
        except (httpx.HTTPError, OSError) as e:
            self._record_failure()
            raise PluginServerUnreachable(f"list_services failed: {e}") from e


# ── Module-level singleton ──────────────────────────────────────

_client: PluginServerClient | None = None
_client_lock = threading.Lock()


def get_plugin_server_client() -> PluginServerClient | None:
    """Get the process-wide PluginServerClient singleton.

    Returns None if PLUGIN_SERVER_ENABLED=0 (legacy in-process
    mode). All other modules should call this and check for None.
    """
    global _client
    if os.environ.get("PLUGIN_SERVER_ENABLED", "1") == "0":
        return None
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = PluginServerClient()
    return _client


def reset_plugin_server_client() -> None:
    global _client
    if _client is not None:
        _client.close()
    _client = None


__all__ = [
    "PluginServerClient",
    "PluginServerError",
    "PluginServerUnreachable",
    "PluginServerCircuitOpen",
    "PluginServerToolError",
    "get_plugin_server_client",
    "reset_plugin_server_client",
]


# ───────────────────────────────────────────────────────────────────
# Panel methods (for /panels/* proxying)
# ───────────────────────────────────────────────────────────────────

def _list_panels_impl(self):
    self._check_circuit()
    try:
        r = self._get_client().get("/panels", timeout=10.0)
        r.raise_for_status()
        self._record_success()
        return r.json()
    except (httpx.HTTPError, OSError) as e:
        self._record_failure()
        raise PluginServerUnreachable(f"list_panels failed: {e}") from e


def _get_panel_impl(self, panel_id, mode="ui"):
    self._check_circuit()
    try:
        r = self._get_client().get(
            f"/panels/{panel_id}", params={"mode": mode}, timeout=10.0
        )
        if r.status_code == 404:
            raise PluginServerError(f"Panel '{panel_id}' not found")
        r.raise_for_status()
        self._record_success()
        return r.json()
    except (httpx.HTTPError, OSError) as e:
        self._record_failure()
        raise PluginServerUnreachable(f"get_panel failed: {e}") from e


def _render_panel_impl(self, panel_id, mode="ui", payload=None):
    self._check_circuit()
    body = {
        "mode": mode,
        "payload": payload or {},
    }
    try:
        r = self._get_client().post(
            f"/panels/{panel_id}/render", json=body, timeout=self.timeout_sec
        )
        if r.status_code == 404:
            raise PluginServerError(f"Panel '{panel_id}' not found")
        if r.status_code == 503:
            try:
                detail = r.json()
            except Exception:
                detail = {"error": r.text}
            self._record_failure()
            raise PluginServerToolError(
                f"panel error: {detail.get('error', 'error')}",
                status_code=503,
                body=detail,
            )
        r.raise_for_status()
        self._record_success()
        return r.json()
    except (httpx.HTTPError, OSError) as e:
        self._record_failure()
        raise PluginServerUnreachable(f"render_panel failed: {e}") from e


# Monkey-patch the methods onto PluginServerClient so they're
# available without needing a full class refactor.
PluginServerClient.list_panels = _list_panels_impl
PluginServerClient.get_panel = _get_panel_impl
PluginServerClient.render_panel = _render_panel_impl
