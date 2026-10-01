"""app/core/router_hot_mount.py
═══════════════════════════════════════════════════════
Live (re)mounting of feature-flag-gated routers on a **running** server.

The problem this exists to solve
════════════════════════════════════
``app/core/routers.py`` prunes ``ROUTER_DEFINITIONS`` by feature flag exactly once,
inside ``register_routers()``, immediately before the ``app.include_router(...)`` loop.
That is the only moment a router is ever mounted. An admin who flips
``set_module_enabled("memory", True)`` therefore gets a flag store that says "on", a
``describe_pruning()`` that reports ``modules.memory is True``, and a server whose
``/api/v1/memory/...`` routes still 404 until restart. The flag state and the actual
behaviour disagree, and nothing tells the operator.

Asymmetry — mounting works, unmounting does not
══════════════════════════════════════════════════════
``app.include_router()`` is valid at any time, so a module can be turned **ON** live.
There is **no supported way to remove a route from a live FastAPI app**. That is not a
gap this module declines to fill — it is a deliberate refusal, because the two available
"removals" are both worse than an honest 409:

* blanking the endpoint callable, or
* mutating ``app.routes``.

Either produces a path that is still listed in ``/openapi.json`` and still routed, but
whose handler does nothing (or 404s only for one method). That is the *reports success it
did not achieve* defect: an admin sees the flag go red, the docs still list the module,
and the failure surfaces later as a mystery 405/500 rather than as a refused toggle.

So the behaviour is split honestly:

* **Enable** → mounted immediately on the live app.
* **Disable** → the flag is written, the write is reported as ``restart_required``, and
  the HTTP 409 names the exact prefixes that are still live. The operator learns the truth
  at the moment of the toggle instead of from a stale OpenAPI page.

Consequences the caller must understand
═══════════════════════════════════════
1. **Startup handlers do not run.** A router carrying ``on_startup`` / ``on_shutdown``
   handlers (or a custom lifespan) is *refused* for a live mount. Those handlers were
   already collected by ``include_router`` during startup and re-running them here could
   double-apply migrations/seeders; not running them would silently half-initialise the
   module. Both are worse than refusing. See :func:`startup_handler_count` — the
   platform currently has exactly one such router (``app/routes/layouts.py``, 2
   handlers) and it declares no ``module``, so it is never prunable and never refused.
2. **OpenAPI is cached.** ``app.openapi_schema`` holds the rendered document and
   ``app/core/openapi.py::custom_openapi`` returns it verbatim when set, so a live mount
   that does not clear it leaves ``/docs`` lying. :func:`invalidate_openapi_cache` clears
   it deliberately after every mutation.
3. **Ordering.** ``include_router`` appends, so a live mount lands *after* every existing
   route. Starlette matches in order, so appending is the shadowing-safe direction — a
   hot-mounted module can never be swallowed by a broad catch-all mounted earlier. The
   mirror risk (the new module being shadowed *by* an earlier broad path) is unchanged from
   startup ordering and is not made worse.
4. **Idempotency.** ``include_router`` called twice with the same prefix duplicates every
   path. The mounted-prefix set lives on ``app.state``, so a retried reconcile is a no-op
   rather than a doubling, and two different apps never share it.
5. **Node catalog is a separate, call-time filter.** ``discover_nodes()`` re-evaluates
   flags on every call, so it tracks the flag more closely than routers ever can. A
   disabled module therefore loses its ``@node`` tools *immediately* while its HTTP
   surface stays up until restart. :func:`reconcile_router_mounts` reports that window
   explicitly as ``node_catalog_divergence`` rather than leaving it to be discovered.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, List, Optional, TypedDict

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import APIRouter, FastAPI

logger = logging.getLogger(__name__)

#: ``app.state`` key holding the set of fully-qualified prefixes already mounted.
MOUNTED_PREFIXES_KEY = "hot_mounted_prefixes"

#: ``app.state`` key holding the unpruned ``ROUTER_DEFINITIONS`` list.
DEFINITIONS_KEY = "router_definitions"

#: ``app.state`` key holding the ``(api_prefix, global_deps)`` the app was built with.
#:
#: A live mount MUST reuse the startup auth dependencies rather than rebuild them. If a
#: caller reconstructed the list from settings and got it wrong (e.g. ``DEV_MODE`` read at
#: a different moment), the hot-mounted router would come up with **no** auth dependency —
#: silently exposing an entire module's surface on a production server. Capturing the real
#: pair at registration time makes that failure impossible by construction.
MOUNT_CONTEXT_KEY = "hot_mount_context"


#: ``app.state`` key holding the set of *mount keys* already mounted.
#:
#: A key is ``"<position>::<full_prefix>"``, NOT the bare prefix. Several registry entries
#: legitimately share one prefix — ``/api/v1/system`` alone carries the system router and
#: the feature-flag listener — so keying the guard on the prefix alone made the second
#: entry a silent no-op reported as ``already_mounted``: a success-looking no-op that
#: left the listener's routes absent. Position is stable because the key is derived from
#: the same recorded ``ROUTER_DEFINITIONS`` list every time.
MOUNT_KEYS_KEY = "hot_mount_keys"


class MountOutcome(TypedDict):
    """Result of attempting one live mount.

    ``action`` is one of:

    * ``mounted`` — ``include_router`` ran; routes are live and OpenAPI was invalidated.
    * ``already_mounted`` — idempotency guard fired; nothing was changed.
    * ``refused`` — the mount was declined with ``reason`` set; nothing was changed.
    """

    prefix: str
    action: str
    reason: Optional[str]
    startup_handlers: int
    key: str


class ReconcileReport(TypedDict):
    """Aggregate outcome of a reconcile pass."""

    mounted: List[MountOutcome]
    already_mounted: List[MountOutcome]
    refused: List[MountOutcome]
    restart_required: List[str]
    node_catalog_divergence: List[str]
    openapi_invalidated: bool


# ═══════════════════════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════════════════════


def mounted_prefixes(app: FastAPI) -> set[str]:
    """Return the live set of fully-qualified prefixes mounted on ``app``.

    Stored on ``app.state`` rather than in a module global so the guard is per-app:
    two apps in one process (the normal shape of a test) cannot suppress each other.
    """
    existing = getattr(app.state, MOUNTED_PREFIXES_KEY, None)
    if existing is None:
        existing = set()
        setattr(app.state, MOUNTED_PREFIXES_KEY, existing)
    return existing


def set_mounted_prefix(app: FastAPI, prefix: str, key: str) -> None:
    """Record ``prefix`` (and its mount ``key``) as mounted on ``app``."""
    mounted_prefixes(app).add(prefix)
    mounted_keys(app).add(key)


def mount_key(position: int, full_prefix: str) -> str:
    """Identity of one registry entry for the idempotency guard.

    Includes the entry's position so two entries sharing a prefix are still distinct —
    ``/api/v1/system`` carries both the system router and the feature-flag listener.
    """
    return f"{position}::{full_prefix}"


def mounted_keys(app: FastAPI) -> set[str]:
    """Return the live set of mount keys already mounted on ``app``."""
    existing = getattr(app.state, MOUNT_KEYS_KEY, None)
    if existing is None:
        existing = set()
        setattr(app.state, MOUNT_KEYS_KEY, existing)
    return existing


def remember_definitions(app: FastAPI, definitions: List[dict]) -> None:
    """Record the unpruned registry list so a later reconcile can re-evaluate it."""
    setattr(app.state, DEFINITIONS_KEY, list(definitions))


def remember_mount_context(
    app: FastAPI, api_prefix: str, global_deps: List[Any]
) -> None:
    """Record the exact prefix + auth deps this app mounted its routers with."""
    setattr(app.state, MOUNT_CONTEXT_KEY, (api_prefix, list(global_deps)))


def mount_context(app: FastAPI) -> Optional[tuple[str, List[Any]]]:
    """Return the recorded ``(api_prefix, global_deps)``, or ``None`` if unknown."""
    return getattr(app.state, MOUNT_CONTEXT_KEY, None)


def registered_definitions(app: FastAPI) -> List[dict]:
    """Return the recorded unpruned registry list (``[]`` if never recorded)."""
    return list(getattr(app.state, DEFINITIONS_KEY, []) or [])


# ═══════════════════════════════════════════════════════════════════════════
# INSPECTION
# ═══════════════════════════════════════════════════════════════════════════


def startup_handler_count(router: APIRouter) -> int:
    """How many startup/shutdown handlers this router contributes to the app.

    ``include_router`` copies ``router.on_startup`` / ``router.on_shutdown`` onto the
    parent app's event handlers. Those fire exactly once, during startup. A router that
    carries any of them cannot be correctly hot-mounted, so :func:`mount_router_entry`
    refuses rather than half-initialising it.
    """
    total = 0
    for attr in ("on_startup", "on_shutdown"):
        handlers = getattr(router, attr, None) or []
        total += len(handlers)
    return total


def invalidate_openapi_cache(app: FastAPI) -> bool:
    """Drop the rendered OpenAPI document so the next ``/openapi.json`` re-renders.

    ``app/core/openapi.py::custom_openapi`` short-circuits on a truthy
    ``app.openapi_schema``, so without this a live mount is invisible in ``/docs`` — the
    operator toggles a flag, hits a route that now works, and ``/docs`` still omits it.
    Returns ``True`` if a cached document was actually discarded.

    FastAPI has used ``openapi_schema`` as the cache attribute since well before the
    pinned 0.128 (this environment reports no ``openapi_cache`` attribute at all), but the
    legacy name is cleared too if some middleware ever installs it.
    """
    discarded = False
    schema = getattr(app, "openapi_schema", None)
    if schema:
        app.openapi_schema = None
        discarded = True
    legacy_cache = getattr(app, "openapi_cache", None)
    if legacy_cache:
        app.openapi_cache = None
        discarded = True
    return discarded


# ═══════════════════════════════════════════════════════════════════════════
# MOUNTING
# ═══════════════════════════════════════════════════════════════════════════


def mount_router_entry(
    app: FastAPI,
    entry: dict,
    api_prefix: str,
    global_deps: List[Any],
    *,
    live: bool = False,
    position: Optional[int] = None,
) -> MountOutcome:
    """Mount one registry ``entry`` onto ``app``, idempotently.

    ``live=True`` declares that the application has already started, which turns on the
    startup-handler refusal. Startup callers pass ``live=False`` (the default) and get the
    plain append behaviour the platform has always had.

    ``position`` is the entry's index in the recorded registry list. It disambiguates
    entries that share a prefix; when omitted (a one-off mount outside the registry) the
    guard falls back to the prefix, which is correct for a standalone entry.

    The app's ``lifespan_context`` is saved and restored around the call: FastAPI's
    ``include_router`` re-wraps it via ``_merge_lifespan_context`` on every invocation.
    ``register_routers`` already does this for the startup loop — a live mount must not
    swap out the context of an app that is already running under it.
    """
    full_prefix = f"{api_prefix}{entry.get('prefix', '')}"
    router = entry["router"]
    handlers = startup_handler_count(router)
    key = (
        mount_key(position, full_prefix)
        if position is not None
        else f"standalone::{full_prefix}::{id(entry)}"
    )

    if key in mounted_keys(app):
        return MountOutcome(
            prefix=full_prefix,
            action="already_mounted",
            reason=None,
            startup_handlers=handlers,
            key=key,
        )

    if live and handlers:
        reason = (
            f"router declares {handlers} startup/shutdown handler(s); those already ran "
            "during startup and re-running them is not safe, so a live mount would "
            "half-initialise the module"
        )
        logger.warning("Refusing live mount of %s: %s", full_prefix, reason)
        return MountOutcome(
            prefix=full_prefix,
            action="refused",
            reason=reason,
            startup_handlers=handlers,
            key=key,
        )

    deps = global_deps if entry.get("auth", True) else []
    orig_lifespan = getattr(app.router, "lifespan_context", None)
    try:
        app.include_router(
            router,
            prefix=full_prefix,
            tags=entry.get("tags", []),
            dependencies=deps,
        )
    finally:
        if orig_lifespan is not None:
            app.router.lifespan_context = orig_lifespan

    set_mounted_prefix(app, full_prefix, key)
    invalidate_openapi_cache(app)
    logger.info("Hot-mounted router %s (live=%s)", full_prefix, live)
    return MountOutcome(
        prefix=full_prefix,
        action="mounted",
        reason=None,
        startup_handlers=handlers,
        key=key,
    )


# ═══════════════════════════════════════════════════════════════════════════
# RECONCILE — the listener body
# ═══════════════════════════════════════════════════════════════════════════


def reconcile_router_mounts(
    app: FastAPI,
    api_prefix: str,
    global_deps: List[Any],
    *,
    live: bool = True,
) -> ReconcileReport:
    """Re-evaluate every prunable registry entry and mount what became enabled.

    Only the *enable* direction acts. A router that is currently mounted but whose flag
    has gone off is reported in ``restart_required`` and left alone — see the module
    docstring for why removal is refused rather than faked.

    ``restart_required`` also surfaces the *node* half of the divergence: the node catalog
    filters at call time, so a module that is off right now has already lost its
    ``@node`` tools even though its HTTP routes remain live.
    """
    from app.core.routers import is_router_enabled

    mounted: List[MountOutcome] = []
    already: List[MountOutcome] = []
    refused: List[MountOutcome] = []
    restart_required: List[str] = []
    divergence: List[str] = []

    definitions = registered_definitions(app)
    if not definitions:
        logger.warning(
            "reconcile_router_mounts: no registry recorded on this app "
            "(register_routers never ran) — nothing to reconcile"
        )

    openapi_invalidated = False
    for position, entry in enumerate(definitions):
        from app.core.routers import router_prune_candidates

        if not router_prune_candidates(entry):
            # Not prunable ⇒ never pruned ⇒ never in scope for a live toggle.
            continue

        full_prefix = f"{api_prefix}{entry.get('prefix', '')}"
        enabled = is_router_enabled(entry)

        if enabled:
            outcome = mount_router_entry(
                app, entry, api_prefix, global_deps, live=live, position=position
            )
            if outcome["action"] == "mounted":
                mounted.append(outcome)
                openapi_invalidated = True
            elif outcome["action"] == "already_mounted":
                already.append(outcome)
            else:
                refused.append(outcome)
            continue

        # Flag is off.
        if full_prefix in mounted_prefixes(app):
            restart_required.append(full_prefix)
        divergence.append(full_prefix)

    if openapi_invalidated:
        # Belt and braces: outcomes above already invalidate per mount, but the report
        # must be true even if a future mount path stops doing it.
        openapi_invalidated = invalidate_openapi_cache(app) or openapi_invalidated

    if mounted or refused or restart_required:
        logger.info(
            "Router reconcile: mounted=%d refused=%d restart_required=%d",
            len(mounted),
            len(refused),
            len(restart_required),
        )

    return ReconcileReport(
        mounted=mounted,
        already_mounted=already,
        refused=refused,
        restart_required=restart_required,
        node_catalog_divergence=divergence,
        openapi_invalidated=openapi_invalidated,
    )


__all__ = [
    "DEFINITIONS_KEY",
    "MOUNT_CONTEXT_KEY",
    "MOUNT_KEYS_KEY",
    "MOUNTED_PREFIXES_KEY",
    "MountOutcome",
    "ReconcileReport",
    "invalidate_openapi_cache",
    "mount_context",
    "mount_key",
    "mount_router_entry",
    "mounted_keys",
    "mounted_prefixes",
    "reconcile_router_mounts",
    "registered_definitions",
    "remember_definitions",
    "remember_mount_context",
    "set_mounted_prefix",
    "startup_handler_count",
]
