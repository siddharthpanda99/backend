"""DF-002 — Decision Fabric feature-flag control plane (`/decision/flags`).

These two endpoints back the UI's `toggleFeatureFlag`. They are ungated by
declaration (``common_lib...decision_engine.flags.ALWAYS_AVAILABLE``) for two
reasons that this file pins:

1. ``GET /flags`` is how a client *learns* the fabric is off. Gating it makes
   the flag unobservable.
2. ``POST /flags/{flag_name}`` is how the master flag is turned back **on**.
   Gating the write would mean that once the fabric was off it could never be
   re-enabled over HTTP.

In exchange for being ungated, the write path refuses the one transition that
would brick the API — disabling ``NEXUS_DECISION_FABRIC_ENABLED`` — with a
typed error and a 400. That refusal is the substance of these tests.

"Ungated" means *not feature-gated*; it is a different concern from
*authorization*. The write route additionally requires the
``decision.flag.set`` permission (see ``TestFlagWriteAuthorization`` below).
These tests exercise the flag semantics, not the RBAC stack, so they opt out
of auth the same way every other route test in this repo does
(``tests/app/modules/ai_models/test_catalog_routes.py`` and friends):
``DISABLE_AUTH`` makes ``require_permission`` short-circuit. The
authorization wiring itself is asserted structurally, without needing a real
identity.
"""

from __future__ import annotations

import os

# Route tests here cover flag semantics, not RBAC. Follow the repo-wide
# convention for exercising a permission-guarded route in isolation.
os.environ.setdefault("DISABLE_AUTH", "true")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from common_lib.modules.decision_engine.flags import (
    DECISION_LEARNING_ENABLED,
    NEXUS_DECISION_FABRIC_ENABLED,
)
from common_lib.modules.integration.ports.rip.rip_port import get_rip_feature_flag_api
from app.modules.decision.routes import router

#: The co-coordination flag. Not protected: it only narrows the surface, and
#: `require_coordination` layers it on top of the master, so it degrades
#: cleanly and can always be re-enabled.
COORDINATION_FLAG = "NEXUS_FF_DECISION_COORDINATION_ENABLED"


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/decision")
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_flags():
    api = get_rip_feature_flag_api()
    assert api is not None
    api["clear_all_overrides"]()
    yield
    api["clear_all_overrides"]()


class TestFlagRead:
    def test_snapshot_lists_every_flag(self, client):
        r = client.get("/api/v1/decision/flags")
        assert r.status_code == 200
        flags = r.json()["flags"]
        assert isinstance(flags, dict)
        assert NEXUS_DECISION_FABRIC_ENABLED in flags
        assert COORDINATION_FLAG in flags
        # Default-OFF: nothing is enabled until an operator says so.
        assert all(v is False for v in flags.values()), flags

    def test_snapshot_reflects_an_override(self, client):
        api = get_rip_feature_flag_api()
        api["set_flag_override"](DECISION_LEARNING_ENABLED, True)
        flags = client.get("/api/v1/decision/flags").json()["flags"]
        assert flags[DECISION_LEARNING_ENABLED] is True


class TestFlagWrite:
    def test_ungated_while_the_fabric_is_off(self, client):
        """The endpoint must answer when the fabric is OFF, not 503.

        This is the whole reason the write path is not guarded: it is the only
        supported way to switch the fabric back on.
        """
        api = get_rip_feature_flag_api()
        api["set_flag_override"](NEXUS_DECISION_FABRIC_ENABLED, False)

        r = client.post(
            f"/api/v1/decision/flags/{NEXUS_DECISION_FABRIC_ENABLED}",
            json={"enabled": True},
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"flag_name": NEXUS_DECISION_FABRIC_ENABLED, "enabled": True}

    def test_master_flag_cannot_be_disabled(self, client):
        r = client.post(
            f"/api/v1/decision/flags/{NEXUS_DECISION_FABRIC_ENABLED}",
            json={"enabled": False},
        )
        assert r.status_code == 400
        assert "cannot be disabled" in r.json()["detail"]

    def test_master_refusal_holds_per_tenant_too(self, client):
        """A tenant-scoped write must not be a way around the refusal."""
        r = client.post(
            f"/api/v1/decision/flags/{NEXUS_DECISION_FABRIC_ENABLED}",
            json={"enabled": False, "tenant_id": "acme"},
        )
        assert r.status_code == 400

    def test_coordination_flag_may_be_disabled(self, client):
        r = client.post(
            f"/api/v1/decision/flags/{COORDINATION_FLAG}", json={"enabled": False}
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    def test_tenant_scoped_write(self, client):
        r = client.post(
            f"/api/v1/decision/flags/{DECISION_LEARNING_ENABLED}",
            json={"enabled": True, "tenant_id": "acme"},
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is True

    def test_unknown_flag_is_rejected(self, client):
        r = client.post("/api/v1/decision/flags/NOT_A_FLAG", json={"enabled": True})
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert "Unknown decision flag" in detail
        # The message must list what IS valid, or the caller cannot recover.
        assert NEXUS_DECISION_FABRIC_ENABLED in detail

    def test_missing_enabled_field_is_422(self, client):
        r = client.post(f"/api/v1/decision/flags/{DECISION_LEARNING_ENABLED}", json={})
        assert r.status_code == 422


class TestGating:
    def test_flag_surface_is_declared_ungated(self):
        """The routes and ``ALWAYS_AVAILABLE`` must not drift apart.

        The module asserts this at import time; re-checking it here means a
        future edit that adds a gated ``/flags*`` route fails as a test too.
        """
        from common_lib.modules.decision_engine.flags import is_route_gated

        flag_paths = {
            route.path for route in router.routes if route.path.startswith("/flags")
        }
        assert flag_paths == {"/flags", "/flags/{flag_name}"}
        assert not any(is_route_gated(p) for p in flag_paths)


class TestFlagWriteAuthorization:
    """The write path is *ungated* but not *unauthorized*.

    These assert the wiring structurally, so the security property survives a
    later refactor even though ``DISABLE_AUTH`` short-circuits the dependency
    at runtime in this module.
    """

    def _post_route(self):
        for route in router.routes:
            if getattr(route, "path", "") == "/flags/{flag_name}":
                return route
        raise AssertionError("POST /flags/{flag_name} is not mounted")

    def test_write_route_requires_a_permission_dependency(self):
        route = self._post_route()
        calls = [
            getattr(dep, "call", None) for dep in route.dependant.dependencies
        ]
        assert calls, "write route has no dependencies — authz was removed"

    def test_read_route_is_not_permission_guarded(self):
        """Reading flags stays open so a client can discover the fabric is off."""
        for route in router.routes:
            if getattr(route, "path", "") == "/flags":
                assert not route.dependant.dependencies
                return
        raise AssertionError("GET /flags is not mounted")
