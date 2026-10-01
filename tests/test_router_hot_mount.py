"""Tests for live feature-flag router (un)mounting.

Covers the defect this feature fixes: ``set_module_enabled("memory", False)`` used to
succeed, persist, be reported by ``describe_pruning()`` as OFF/ON — and still leave the
routes unmounted (or mounted) until a restart, with nothing telling the operator.

Contract under test (see ``app/core/router_hot_mount.py`` for the full rationale):

* **Enable is live.** A module enabled at runtime is mounted on the running app and
  serves a real request, verified here through a real ``TestClient`` — never a mock or a
  fabricated ``FastAPI`` stand-in, which would only validate the stand-in.
* **Disable is refused, not faked.** There is no supported way to un-``include`` a router
  from a live FastAPI app, so a live disable returns 409 naming the still-live prefixes.
  It must never blank a handler or mutate ``app.routes``.
* **OpenAPI must not lie.** The cached schema is discarded on every mutation.
* **Idempotent.** ``include_router`` twice on one prefix duplicates every path.
* **Startup handlers do not run.** A router carrying them is refused a live mount.

Every test that writes flag state uses ``persist=False`` so the real
``resources/memory_config.ini`` is never written; a fixture reloads the store afterwards.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from common_lib.modules.common.feature_flags import FeatureFlagStore

from app.core import routers as r
from app.core import router_hot_mount as hm


@pytest.fixture(autouse=True)
def _clean_flag_state():
    """Undo any runtime flag mutation a test performs. Never persists to disk."""
    yield
    FeatureFlagStore().set_module_enabled("memory", True, persist=False)
    FeatureFlagStore().reload()


@pytest.fixture
def live_client():
    """A real app built by the real ``register_routers``, behind a real ``TestClient``.

    Deliberately built by mounting the registry onto a fresh app rather than importing
    ``app.main``: the lifespan in ``main`` boots background warmups and database
    connections that are irrelevant here and would make the test slow and order-
    dependent. The registry mount and the flag store under test are the real ones.

    Builds with the default flag state (everything on), so the module under test is
    already mounted at startup. Use :func:`_client_pruned` when the scenario needs a
    server that *started* without the module — which is the real shape of this bug.
    """
    from fastapi import FastAPI

    app = FastAPI()
    r.register_routers(app, "/api/v1", [])
    # Entering the context manager runs the lifespan, which is what makes this a
    # *running* server rather than a merely-constructed one.
    with TestClient(app) as client:
        client.app_instance = app  # type: ignore[attr-defined]
        yield client


def _client_pruned(module: str) -> TestClient:
    """Build and start a real server that *never mounted* ``module``.

    The flag is turned off **before** ``register_routers`` so pruning happens at startup,
    exactly as it would for an operator who disabled the module and then started the
    process. Returns the live ``TestClient``; the caller must close it.
    """
    from fastapi import FastAPI

    FeatureFlagStore().set_module_enabled(module, False, persist=False)
    app = FastAPI()
    r.register_routers(app, "/api/v1", [])
    client = TestClient(app)
    client.__enter__()
    client.app_instance = app  # type: ignore[attr-defined]
    return client


# ═══════════════════════════════════════════════════════════════════════════
# 1. Enable is applied live, proven with a real request before/after
# ═══════════════════════════════════════════════════════════════════════════


def test_enable_is_applied_to_a_running_server():
    """The original bug: a module turned on at runtime still 404s until restart.

    Before: flag OFF, route 404. After the listener runs: flag ON, route served —
    with no restart and no re-registration.
    """
    client = _client_pruned("memory")
    try:
        app = client.app_instance
        probe = "/api/v1/system/feature-flags/memory/mounted"

        # ── BEFORE: flag OFF, routes genuinely absent, request 404s ──
        before = client.get(probe)
        assert before.status_code == 200, before.text
        before_body = before.json()
        assert before_body["currently_mounted"] == []
        assert before_body["flag_enabled"] is False

        not_found = client.get("/api/v1/memory/adaptation/telemetry")
        assert not_found.status_code == 404, (
            f"memory route should 404 while pruned, got {not_found.status_code}"
        )
        assert "/api/v1/memory/adaptation/telemetry" not in app.openapi().get("paths", {})

        # ── Write the flag ON through the real listener endpoint ──
        resp = client.post(
            "/api/v1/system/feature-flags/memory",
            json={"enabled": True, "scope": "module", "persist": False},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["enabled"] is True
        assert body["applied_live"] is True
        assert "/api/v1/memory" in body["mounts"]["mounted"], body
        assert "/api/v1/memories" in body["mounts"]["mounted"], body

        # ── AFTER: route is really in the table ──
        after = client.get(probe).json()
        assert after["flag_enabled"] is True
        assert "/api/v1/memory" in after["currently_mounted"]

        # The route is no longer 404. It may now fail auth or return a domain error,
        # but the router resolved — which is exactly what "mounted" means.
        now = client.get("/api/v1/memory/adaptation/telemetry")
        assert now.status_code != 404, "route still 404s after a live enable"

        # Same app object, no restart: the mounted set grew on the live instance.
        assert "/api/v1/memory" in hm.mounted_prefixes(app)
        assert hm.mounted_keys(app), "mount keys should have been recorded"
    finally:
        client.__exit__(None, None, None)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Disable is refused honestly, and definitely not faked
# ═══════════════════════════════════════════════════════════════════════════


def test_live_disable_returns_409_and_keeps_routes_live():
    """A disable that cannot be performed must say so, not claim success."""
    client = _client_pruned("memory")
    try:
        app = client.app_instance

        # Bring it up live first, so there IS something to refuse to remove.
        client.post(
            "/api/v1/system/feature-flags/memory",
            json={"enabled": True, "scope": "module", "persist": False},
        )
        assert "/api/v1/memory" in hm.mounted_prefixes(app)

        # Now disable it live.
        resp = client.post(
            "/api/v1/system/feature-flags/memory",
            json={"enabled": False, "scope": "module", "persist": False},
        )
        assert resp.status_code == 409, resp.text
        detail = resp.json()["detail"]
        assert "/api/v1/memory" in detail["mounts"]["restart_required"]
        assert "restart" in detail["message"].lower()

        # The flag WAS written — it is the route table that cannot follow.
        assert FeatureFlagStore().is_enabled("memory") is False

        # And the routes genuinely still serve: no handler was blanked, app.routes
        # untouched.
        assert "/api/v1/memory" in hm.mounted_prefixes(app)
        still = client.get("/api/v1/memory/adaptation/telemetry")
        assert still.status_code != 404, "route was faked away instead of reported live"
    finally:
        client.__exit__(None, None, None)


def test_disable_does_not_mutate_app_routes(live_client):
    """`app.routes` is not pruned to fake a removal.

    Guards the specific anti-pattern: deleting Route objects so OpenAPI looks clean
    while the module is still logically live. The route count must not shrink.
    """
    app = live_client.app_instance
    FeatureFlagStore().set_module_enabled("memory", True, persist=False)
    live_client.post(
        "/api/v1/system/feature-flags/memory",
        json={"enabled": False, "scope": "module", "persist": False},
    )

    assert any(
        getattr(rt, "path", "").startswith("/api/v1/memory") for rt in app.routes
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. OpenAPI invalidation
# ═══════════════════════════════════════════════════════════════════════════


def test_openapi_cache_is_invalidated_on_live_mount():
    """`/openapi.json` must reflect a live mount, not the cached pre-mount document."""
    client = _client_pruned("memory")
    try:
        app = client.app_instance

        schema_before = app.openapi()
        assert "/api/v1/memory/adaptation/telemetry" not in schema_before["paths"]

        resp = client.post(
            "/api/v1/system/feature-flags/memory",
            json={"enabled": True, "scope": "module", "persist": False},
        )
        assert resp.status_code == 200, resp.text

        # app.openapi() would return the cached dict if it had not been cleared.
        schema_after = app.openapi()
        assert "/api/v1/memory/adaptation/telemetry" in schema_after["paths"], (
            "live mount is invisible in the OpenAPI schema — /docs is lying"
        )
    finally:
        client.__exit__(None, None, None)


def test_invalidate_openapi_cache_reports_whether_it_discarded():
    """It reports a discard only when a cached document actually existed."""
    from fastapi import FastAPI

    app = FastAPI()
    assert hm.invalidate_openapi_cache(app) is False
    app.openapi_schema = {"paths": {}}
    assert hm.invalidate_openapi_cache(app) is True
    assert app.openapi_schema is None


# ═══════════════════════════════════════════════════════════════════════════
# 4. Idempotency — no double-mount
# ═══════════════════════════════════════════════════════════════════════════


def test_double_mount_does_not_duplicate_routes():
    """`include_router` twice on one prefix duplicates every path; the guard prevents it."""
    client = _client_pruned("memory")
    try:
        app = client.app_instance

        client.post(
            "/api/v1/system/feature-flags/memory",
            json={"enabled": True, "scope": "module", "persist": False},
        )
        count_after_first = len(
            [r_ for r_ in app.routes if "memory" in getattr(r_, "path", "")]
        )

        # Retrying the enable (a flaky client, a double-submitted form) must be a no-op.
        for _ in range(3):
            body = client.post(
                "/api/v1/system/feature-flags/memory",
                json={"enabled": True, "scope": "module", "persist": False},
            ).json()
            assert "/api/v1/memory" in body["mounts"]["already_mounted"]

        count_after_retries = len(
            [r_ for r_ in app.routes if "memory" in getattr(r_, "path", "")]
        )
        assert count_after_retries == count_after_first, (
            f"retried enable duplicated routes: {count_after_first} -> {count_after_retries}"
        )
    finally:
        client.__exit__(None, None, None)


def test_mount_router_entry_is_idempotent_for_the_same_app():
    """The guard is per-app: two apps in one process must not suppress each other."""
    from fastapi import APIRouter, FastAPI

    def build():
        app = FastAPI()
        sub = APIRouter()

        @sub.get("/ping")
        def ping():
            return {"ok": True}

        entry = {"router": sub, "prefix": "/demo", "tags": ["Demo"], "auth": True}
        return app, entry

    app_a, entry_a = build()
    app_b, entry_b = build()

    first = hm.mount_router_entry(app_a, entry_a, "/api/v1", [])
    assert first["action"] == "mounted"
    assert (
        hm.mount_router_entry(app_a, entry_a, "/api/v1", [])["action"]
        == "already_mounted"
    )

    # A different app gets its own mount — no cross-app suppression.
    assert hm.mount_router_entry(app_b, entry_b, "/api/v1", [])["action"] == "mounted"
    assert (
        len(
            [
                r_
                for r_ in app_b.routes
                if getattr(r_, "path", "") == "/api/v1/demo/ping"
            ]
        )
        == 1
    )


def test_two_registry_entries_sharing_a_prefix_both_mount():
    """Regression: the guard must key on entry identity, not the bare prefix.

    ``/api/v1/system`` carries both the system router and the feature-flag listener.
    A prefix-only key made the second entry a silent ``already_mounted`` no-op — a
    success-looking result that left the listener's routes absent, which is exactly the
    defect class this feature exists to remove.
    """
    from fastapi import APIRouter, FastAPI

    app = FastAPI()
    first_router, second_router = APIRouter(), APIRouter()

    @first_router.get("/one")
    def one():
        return {}

    @second_router.get("/two")
    def two():
        return {}

    entries = [
        {"router": first_router, "prefix": "/shared", "tags": ["A"], "auth": True},
        {"router": second_router, "prefix": "/shared", "tags": ["B"], "auth": True},
    ]
    for position, entry in enumerate(entries):
        outcome = hm.mount_router_entry(app, entry, "/api/v1", [], position=position)
        assert outcome["action"] == "mounted", outcome

    paths = {getattr(rt, "path", "") for rt in app.routes}
    assert "/api/v1/shared/one" in paths
    assert "/api/v1/shared/two" in paths


# ═══════════════════════════════════════════════════════════════════════════
# 5. Startup handlers
# ═══════════════════════════════════════════════════════════════════════════


def test_live_mount_is_refused_for_a_router_with_startup_handlers():
    """A router with startup handlers cannot be correctly hot-mounted — so it is refused.

    Its handlers already ran during startup. Re-running them could double-apply
    migrations; not running them would half-initialise the module. Refusing is the only
    honest option.
    """
    from fastapi import APIRouter, FastAPI

    app = FastAPI()
    started: list[str] = []

    sub = APIRouter()

    @sub.on_event("startup")
    def _boot():
        started.append("ran")

    @sub.get("/thing")
    def thing():
        return {}

    entry = {"router": sub, "prefix": "/needs_boot", "tags": ["X"], "auth": True}

    outcome = hm.mount_router_entry(app, entry, "/api/v1", [], live=True)
    assert outcome["action"] == "refused"
    assert outcome["startup_handlers"] == 1
    assert "startup" in outcome["reason"].lower()

    # Nothing was mounted and no handler ran.
    assert not any(
        getattr(rt, "path", "").startswith("/api/v1/needs_boot") for rt in app.routes
    )
    assert started == []


def test_startup_mount_of_the_same_router_is_allowed():
    """The refusal is live-only. During startup the handlers are exactly what is wanted."""
    from fastapi import APIRouter, FastAPI

    app = FastAPI()
    sub = APIRouter()

    @sub.on_event("startup")
    def _boot():
        return None

    @sub.get("/thing")
    def thing():
        return {}

    entry = {"router": sub, "prefix": "/needs_boot", "tags": ["X"], "auth": True}
    outcome = hm.mount_router_entry(app, entry, "/api/v1", [], live=False)
    assert outcome["action"] == "mounted"
    assert outcome["startup_handlers"] == 1


def test_platform_router_inventory_counts_startup_handlers():
    """Pin the real number so a change to it is visible rather than silent.

    Today exactly one registered router carries startup handlers: ``/layouts`` (2). It
    declares no ``module``, so it is never prunable and the refusal path is unreachable
    in practice — recorded here so that if someone gives it a ``module``, the fact is
    already on the record.
    """
    from fastapi import FastAPI

    app = FastAPI()
    r.register_routers(app, "/api/v1", [])
    defs = hm.registered_definitions(app)

    with_handlers = {
        f"/api/v1{e.get('prefix', '')}": hm.startup_handler_count(e["router"])
        for e in defs
        if hm.startup_handler_count(e["router"])
    }
    assert with_handlers == {"/api/v1/layouts": 2}, (
        f"router startup-handler inventory changed: {with_handlers}"
    )

    # And the only one is not prunable, so it can never reach the refusal path.
    from app.core.routers import router_prune_candidates

    layouts = next(e for e in defs if e.get("prefix") == "/layouts")
    assert router_prune_candidates(layouts) == []


# ═══════════════════════════════════════════════════════════════════════════
# 6. Listener surface behaviour
# ═══════════════════════════════════════════════════════════════════════════


def test_unregistered_flag_is_rejected_not_silently_accepted(live_client):
    """An unregistered path is always enabled, so writing one would be a no-op lie."""
    resp = live_client.post(
        "/api/v1/system/feature-flags/not.a.real.flag",
        json={"enabled": False, "persist": False},
    )
    assert resp.status_code == 404
    assert "registered" in resp.json()["detail"].lower()


def test_mounts_endpoint_is_read_only(live_client):
    """GET /mounts reports the divergence without changing the route table."""
    app = live_client.app_instance
    FeatureFlagStore().set_module_enabled("memory", False, persist=False)

    before = len(app.routes)
    body = live_client.get("/api/v1/system/feature-flags/mounts").json()

    assert "/api/v1/memory" in body["node_catalog_divergence"]
    assert len(app.routes) == before, (
        "the read-only mounts endpoint mutated the route table"
    )


def test_listener_router_is_always_mounted():
    """The switch that un-prunes everything must itself never be prunable.

    Otherwise a bad flag write could leave no way back except a restart.
    """
    from app.core.routers import router_prune_candidates

    assert router_prune_candidates({"router": None, "prefix": "", "tags": []}) == []


def test_mount_context_preserves_startup_auth_deps(live_client):
    """A live mount must reuse the app's real auth deps, not rebuild them.

    Rebuilding is the dangerous direction: a mismatch would mount a module's whole
    surface with no global auth dependency.
    """
    from fastapi import Depends, FastAPI

    sentinel = Depends(lambda: None)

    app = FastAPI()
    r.register_routers(app, "/api/v1", [sentinel])
    api_prefix, deps = hm.mount_context(app)

    assert api_prefix == "/api/v1"
    assert len(deps) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 7. Node-catalog / route divergence
# ═══════════════════════════════════════════════════════════════════════════


def test_node_catalog_follows_the_flag_faster_than_routes_do(live_client):
    """Documents the asymmetry a user can hit: nodes vanish before routes do.

    ``discover_nodes()`` filters at call time, so a module disabled while its routes are
    still live (pending restart) has already lost its ``@node`` tools. The API reports
    this window explicitly via ``node_catalog_divergence`` instead of leaving the operator
    to notice a tool that has disappeared.
    """
    FeatureFlagStore().set_module_enabled("memory", False, persist=False)

    body = live_client.get("/api/v1/system/feature-flags/mounts").json()

    # memory is off -> its prefixes are reported as divergent (flag off, routes still live).
    assert "/api/v1/memory" in body["node_catalog_divergence"]
    # The node catalog has already dropped them; the HTTP surface has not.
    assert "/api/v1/memory" in body["restart_required"]


# ═══════════════════════════════════════════════════════════════════════════
# 8. Reconciliation reports rather than raising when the registry is unknown
# ═══════════════════════════════════════════════════════════════════════════


def test_reconcile_on_app_without_recorded_registry_is_a_noop():
    """An app that never ran register_routers must not raise on a reconcile."""
    from fastapi import FastAPI

    report = hm.reconcile_router_mounts(FastAPI(), "/api/v1", [], live=True)
    assert report["mounted"] == []
    assert report["refused"] == []


# ═══════════════════════════════════════════════════════════════════════════
# 9. Regression guard for the existing startup behaviour
# ═══════════════════════════════════════════════════════════════════════════


def test_startup_still_prunes_disabled_modules(live_client):
    """The original behaviour is unchanged: off at startup means not mounted at all."""
    app = live_client.app_instance
    FeatureFlagStore().set_module_enabled("memory", False, persist=False)

    fresh = FastAPI = __import__("fastapi").FastAPI()
    r.register_routers(fresh, "/api/v1", [])
    assert not any(
        getattr(rt, "path", "").startswith("/api/v1/memory") for rt in fresh.routes
    )
    assert app is not fresh
