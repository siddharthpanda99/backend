"""On-demand mounting of deferred router entries.

``ROUTER_DEFINITIONS`` marks module routers as deferred. Historically they
were mounted right after bind by ``register_routers_background`` — that
imports every module (torch, media stacks, …) at startup even when nothing
ever calls their APIs, and the startup path paid the same import cost on
the post-bind thread.

Instead, this middleware hot-mounts a deferred entry the first time a
request matches its prefix (``mount_router_entry`` is an ``include_router``
call — milliseconds). The first call to a module's route pays a trivial
cost; modules nobody calls never load at all — less RAM at startup and a
faster "server is up" moment.

Routers that cannot be live-mounted (their router declares startup
handlers that already ran during startup) fall back to a live=False mount
so their routes stay reachable.
"""

import logging

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.router_hot_mount import mount_router_entry, registered_definitions

logger = logging.getLogger(__name__)


def _matches(path: str, prefix: str) -> bool:
    """True when ``path`` is ``prefix`` or a request under it."""
    if not prefix:
        return True
    trimmed = prefix.rstrip("/")
    return path == trimmed or path.startswith(trimmed + "/")


class LazyMountMiddleware:
    """ASGI middleware that mounts deferred entries on first request.

    One set of deferred entries lives on ``app.state._deferred_router_entries``
    (see ``app/main.py`` ``create_app``); the middleware mounts each entry
    whose prefix matches the incoming request path before dispatching.
    """

    def __init__(
        self,
        app: ASGIApp,
        api_prefix: str,
        global_deps: list,
        get_entries,
        target_app,
    ):
        # ``app`` is the inner ASGI chain (the middleware wraps CORS etc.);
        # ``target_app`` is the FastAPI instance — mount operations need it.
        self.app = app
        self.target_app = target_app
        self.api_prefix = api_prefix
        self.global_deps = global_deps
        self._get_entries = get_entries
        self._tried: set[int] = set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            try:
                self._mount_matching(scope.get("path", ""))
            except Exception:  # noqa: BLE001 — mounting must never 500 a request
                logger.error(
                    "lazy mount scan failed for %s",
                    scope.get("path"),
                    exc_info=True,
                )
        await self.app(scope, receive, send)

    def _mount_matching(self, path: str) -> None:
        entries = self._get_entries() or []
        full_prefixes = [
            f"{self.api_prefix}{entry.get('prefix', '')}" for entry in entries
        ]
        matches = [full for full in full_prefixes if _matches(path, full)]
        logger.debug(
            "LazyMount: path=%s entries=%d matches=%s",
            path,
            len(entries),
            matches[:6],
        )
        if not matches:
            return
        positions = {
            id(entry): index
            for index, entry in enumerate(registered_definitions(self.target_app) or [])
        }
        for entry in entries:
            full_prefix = f"{self.api_prefix}{entry.get('prefix', '')}"
            if not _matches(path, full_prefix):
                continue
            key = id(entry)
            if key in self._tried:
                continue
            self._tried.add(key)
            logger.debug(
                "LazyMount: attempting mount for path=%s prefix=%s",
                path,
                full_prefix,
            )
            position = positions.get(key)
            try:
                outcome = mount_router_entry(
                    self.target_app,
                    entry,
                    self.api_prefix,
                    self.global_deps,
                    live=True,
                    position=position,
                )
            except Exception:  # noqa: BLE001
                logger.exception("lazy mount raised for %s", full_prefix)
                continue
            if outcome["action"] == "refused":
                # Startup handlers already ran — mounting live would skip
                # them — so mount without them, like the old background pass.
                mount_router_entry(
                    self.target_app,
                    entry,
                    self.api_prefix,
                    self.global_deps,
                    live=False,
                    position=position,
                )
                logger.info("Hot-mounted router %s (live=False)", full_prefix)
            elif outcome["action"] == "mounted":
                logger.info("Lazily mounted router %s", full_prefix)
