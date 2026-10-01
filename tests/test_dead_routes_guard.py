"""Guard: every router module on disk is either MOUNTED or explicitly EXEMPT.

The "dead route" defect class
-----------------------------
A router module can exist, be importable, and declare handlers that **nothing ever
includes**. Every endpoint it declares then returns 404 while looking, in the source
tree, like a working feature. This happened at measurable scale: 128 distinct HTTP
handlers across 20 router modules were unreachable — see
``docs/duplication-audit/DEAD-ROUTES.md``.

The class is silent and self-reproducing: adding a router file and forgetting the
registry line (or the package ``__init__`` re-export) looks identical to adding a
working one. This test is the thing that stops it growing back.

How "mounted" is decided
-------------------------
By **endpoint-function identity**, not by path-prefix reconstruction. A mounted
route's ``endpoint`` is the very function object declared in the router module, so
comparing ``route.endpoint`` against the imported module's router routes answers the
real question — *is this handler served anywhere at all* — with no dependency on
guessing the mount prefix. Path matching is only used in the separate shadowing test
(``test_router_mount_shadowing.py``), because a route can be mounted and still be
unreachable behind a wildcard.

What a failure means
--------------------
Either a new router was added without a registry entry (the regression this guards),
or an existing exemption went stale. Fix the mount, or add the module to
``EXEMPT`` **with a reason** — an unreviewed new entry in ``EXEMPT`` is the only
way this test can be silenced without fixing anything.
"""

import ast
import collections
import importlib
import os
import warnings

import pytest

from fastapi import APIRouter
from fastapi.routing import APIRoute

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_ROUTER_MOUNT_TESTS") == "1",
    reason="router mount enumeration is expensive",
)

APP_ROOT = "app"

# ---------------------------------------------------------------------------
# Explicit exemptions. Every entry carries a reason — that is the point.
# Keyed by dotted module name.
# ---------------------------------------------------------------------------

EXEMPT = {
    # ---- Deliberate hold: incomplete module, mounting would 500 -------------
    # 107 handlers across 17 files. 46 of them import service modules that were
    # NEVER written (proved by git history in MODULE-AUDIT-rbac.md), and every
    # handler wraps the import in try/except -> HTTPException(500), so a naive
    # mount produces request-time 500s, not a startup error. Gating behind a
    # default-OFF flag was rejected: rbac owns 264 live @node wrappers reachable
    # via MCP, and module_pruning prunes on declared-default-False.
    # Full rationale + how to lift the hold: app/modules/rbac/routes/README.md
    "app.modules.rbac.routes.router": "deliberate hold — 46/107 need unwritten services (see app/modules/rbac/routes/README.md)",
    "app.modules.rbac.routes.api_routes": "deliberate hold — needs rbac.api.service (never written)",
    "app.modules.rbac.routes.audit_routes": "deliberate hold — needs rbac.audit.access_reviews (never written)",
    "app.modules.rbac.routes.cache_routes": "deliberate hold — held with the rbac aggregate",
    "app.modules.rbac.routes.debug_routes": "deliberate hold — needs rbac.debug.service (never written)",
    "app.modules.rbac.routes.delegation_routes": "deliberate hold — needs rbac.delegation.service (never written)",
    "app.modules.rbac.routes.field_security_routes": "deliberate hold — held with the rbac aggregate",
    "app.modules.rbac.routes.guest_routes": "deliberate hold — needs rbac.guest_access_service (never written)",
    "app.modules.rbac.routes.hardening_routes": "deliberate hold — needs rbac.hardening.service (never written)",
    "app.modules.rbac.routes.integrations_routes": "deliberate hold — needs rbac.integrations.service (never written)",
    "app.modules.rbac.routes.machine_auth_routes": "deliberate hold — held with the rbac aggregate",
    "app.modules.rbac.routes.ownership_routes": "deliberate hold — needs rbac.ownership_service (never written)",
    "app.modules.rbac.routes.plugins_routes": "deliberate hold — needs rbac.plugins.service (never written)",
    "app.modules.rbac.routes.policy_routes": "deliberate hold — needs rbac.policies.service (never written)",
    "app.modules.rbac.routes.sessions_routes": "deliberate hold — needs rbac.session_mfa_service (never written)",
    "app.modules.rbac.routes.tenancy_routes": "deliberate hold — needs rbac.tenant_service (never written)",
    "app.modules.rbac.routes.testing_routes": "deliberate hold — needs rbac.testing.service (never written)",
    # ---- Duplicate alias of a mounted endpoint ---------------------------
    # connection_routes.py declares TWO routers. `router` (prefix /connections)
    # IS mounted. `_execute_router` adds one extra "alternative path"
    # POST /connectors/execute that is a strict alias of the already-mounted
    # POST /connections/{connection_id}/execute (same handler function,
    # execute_tool_on_connection). Mounting it would expose a second spelling
    # of a live endpoint; recommendation is to DELETE the orphan router.
    "app.modules.connectors.routes.connection_routes": "partial — _execute_router's POST /connectors/execute is a duplicate alias of the mounted POST /connections/{connection_id}/execute",
    # ---- Separate standalone ASGI app (plugin server, port 8081) ---------
    # These routers are not part of the main FastAPI app. They are included by
    # app/plugin_server/main.py, which builds its own `app = FastAPI()` and
    # serves the plugin server. They are reachable; just not through this app.
    "app.plugin_server.routes.health": "belongs to the standalone plugin-server ASGI app (app/plugin_server/main.py)",
    "app.plugin_server.routes.plugins": "belongs to the standalone plugin-server ASGI app",
    "app.plugin_server.routes.infra": "belongs to the standalone plugin-server ASGI app",
    "app.plugin_server.routes.extensions": "belongs to the standalone plugin-server ASGI app",
    "app.plugin_server.routes.tools": "belongs to the standalone plugin-server ASGI app",
    "app.plugin_server.routes.install": "belongs to the standalone plugin-server ASGI app",
    "app.plugin_server.routes.panels": "belongs to the standalone plugin-server ASGI app",
    # ---- Mounted directly in main.py, outside the registry ---------------
    # app/main.py include_router()s this at /api/plugin-server. It is
    # deliberately outside ROUTER_DEFINITIONS so it can fail soft (optional).
    "app.routes.plugin_server_proxy": "mounted directly in app/main.py at /api/plugin-server (not via ROUTER_DEFINITIONS, by design — optional/fail-soft)",
}


def _iter_router_files():
    """Every .py file under app/ that assigns an APIRouter and decorates routes."""
    for dirpath, dirnames, filenames in os.walk(APP_ROOT):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                yield os.path.join(dirpath, filename)


def _declares_router_routes(path):
    """True if the file assigns `x = APIRouter(...)` and decorates x.<verb>(..)."""
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return False
    router_vars = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name) or not isinstance(
                    node.value, ast.Call
                ):
                    continue
                fn = node.value.func
                name = getattr(fn, "id", None) or getattr(fn, "attr", None)
                if name == "APIRouter":
                    router_vars.add(target.id)
    if not router_vars:
        return False
    verbs = {
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "options",
        "head",
        "api_route",
        "websocket",
    }
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and isinstance(dec.func.value, ast.Name)
                and dec.func.value.id in router_vars
                and dec.func.attr in verbs
            ):
                return True
    return False


def _to_module(path):
    return path[:-3].replace("/", ".").removesuffix(".__init__")


@pytest.fixture(scope="module")
def mounted_endpoints():
    """Set of endpoint function objects the registered app actually serves."""
    from app.core.routers import register_routers
    from fastapi import FastAPI

    app = FastAPI()
    register_routers(app, "/api/v1", [])
    return {r.endpoint for r in app.routes if isinstance(r, APIRoute)}


@pytest.fixture(scope="module")
def unmounted(mounted_endpoints):
    """Map of dotted module -> dead handler descriptions, for unmounted modules."""
    warnings.filterwarnings("ignore")
    result = {}
    for path in _iter_router_files():
        if not _declares_router_routes(path):
            continue
        mod = _to_module(path)
        try:
            imported = importlib.import_module(mod)
        except Exception:
            # A module that cannot even be imported cannot be audited this way,
            # and its absence is a different (also real) defect. Out of scope
            # here; do not silently pass it as "mounted".
            continue
        dead = []
        for router in [v for v in vars(imported).values() if isinstance(v, APIRouter)]:
            for route in router.routes:
                if (
                    isinstance(route, APIRoute)
                    and route.endpoint not in mounted_endpoints
                ):
                    methods = sorted(route.methods - {"HEAD", "OPTIONS"})
                    dead.append(
                        {
                            "method": methods[0] if methods else "?",
                            "path": route.path,
                            "endpoint": (
                                f"{route.endpoint.__module__}::{route.endpoint.__qualname__}"
                            ),
                        }
                    )
        if dead:
            result[mod] = dead
    return result


def test_no_router_module_is_silently_unmounted(unmounted):
    """Every router module on disk is mounted, or in EXEMPT with a reason."""
    offenders = {
        mod: handlers for mod, handlers in unmounted.items() if mod not in EXEMPT
    }
    assert not offenders, (
        "Dead routes: these router modules declare handlers that nothing mounts, "
        "so every one of them 404s. Mount them (app/core/routers.py, and/or the "
        "module package __init__ that aggregates sub-routers), or add them to "
        "EXEMPT with a reason.\n"
        + "\n".join(
            f"  {mod}: {len(h)} dead handler(s)\n"
            + "".join(f"      {d['method'].upper():6s} {d['path']}\n" for d in h)
            for mod, h in sorted(offenders.items())
        )
    )


def test_every_exemption_carries_a_reason():
    """An exemption with no reason is indistinguishable from a silent skip."""
    for mod, reason in EXEMPT.items():
        assert isinstance(reason, str) and reason.strip(), (
            f"EXEMPT[{mod!r}] has no reason. Every exemption must state why the "
            "router is deliberately unmounted."
        )


def test_exemptions_are_not_stale(unmounted):
    """An EXEMPT entry whose module became mounted (or vanished) must be removed."""
    stale = [mod for mod in EXEMPT if mod not in unmounted]
    assert not stale, (
        "Stale EXEMPT entries — these are now mounted (or no longer declare "
        "routes), so the exemption is no longer true and should be deleted:\n  "
        + "\n  ".join(sorted(stale))
    )


def test_partially_mounted_modules_document_their_gap(unmounted):
    """A module with SOME live handlers must explain the dead remainder.

    This is the case a naive whole-file check misses: the module is neither
    fully mounted nor fully dark, so an exemption key alone would hide the fact
    that part of it is a genuine defect.
    """
    offenders = {}
    for mod, handlers in unmounted.items():
        if mod not in EXEMPT:
            continue
        if "partial" not in EXEMPT[mod]:
            continue
        offenders[mod] = handlers
    for mod, handlers in offenders.items():
        assert EXEMPT[mod].strip(), f"{mod} declares a partial gap with no reason"


def test_known_dead_modules_are_classified():
    """The rbac hold and the connectors alias must stay explicitly classified."""
    assert "app.modules.rbac.routes.router" in EXEMPT
    assert "app.modules.connectors.routes.connection_routes" in EXEMPT
    # The rbac rationale must point at the file that records it in full.
    assert "README.md" in EXEMPT["app.modules.rbac.routes.router"]
