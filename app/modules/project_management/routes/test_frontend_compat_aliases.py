"""Frontend-compatibility alias tests for the project_management surface.

WHY THIS EXISTS
---------------
`platform-demo`'s Project Management hooks request a set of paths the
backend never registered. 11 of those request sites resolve to 404 for
every verb -- a routing-404, distinct from a domain-404 (route exists,
resource absent). The frontend submodule is owned by another session,
so this side repairs what is unambiguously a path-shape mismatch on
paths that DO have a backend counterpart, additively.

The canonical single-segment spellings are asserted to still resolve:
these aliases must never *replace* a route (rule: extend, never
replace).

These tests are falsifiable. Deleting either `include_router` call in
`app/modules/project_management/routes/index.py` turns
`test_finance_compat_alias_resolves` RED; removing the canonical mount
turns `test_canonical_finance_paths_still_resolve` RED.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.project_management.routes.index import router as pm_router

# Paths the frontend requests under /finance/*. Each entry is
# (path, verb) and each must NOT 404 -- a 405/422/500 means the route
# is mounted (wrong verb / missing body / no DB in this env), which is
# the routing-vs-domain distinction this suite exists to keep honest.
FINANCE_ALIAS_SITES: list[tuple[str, str]] = [
    ("/api/v1/pm/finance/budgets", "GET"),
    ("/api/v1/pm/finance/budgets", "POST"),
    ("/api/v1/pm/finance/budgets/{id}", "GET"),
    ("/api/v1/pm/finance/budgets/{id}", "PATCH"),
    ("/api/v1/pm/finance/budgets/summary/{id}", "GET"),
    ("/api/v1/pm/finance/costs", "POST"),
    ("/api/v1/pm/finance/costs/summary/{id}", "GET"),
    ("/api/v1/pm/finance/evm/compute/{id}", "GET"),
    ("/api/v1/pm/finance/vendors", "GET"),
    ("/api/v1/pm/finance/vendors", "POST"),
    ("/api/v1/pm/finance/vendors/{id}", "DELETE"),
    ("/api/v1/pm/finance/purchase-requests", "GET"),
    ("/api/v1/pm/finance/purchase-requests", "POST"),
    ("/api/v1/pm/finance/purchase-requests/{id}/approve", "POST"),
]

# The canonical (pre-existing) spellings. None of these may regress.
CANONICAL_FINANCE_SITES: list[tuple[str, str]] = [
    ("/api/v1/pm/budgets", "GET"),
    ("/api/v1/pm/budgets", "POST"),
    ("/api/v1/pm/budgets/{id}", "GET"),
    ("/api/v1/pm/budgets/{id}", "PATCH"),
    ("/api/v1/pm/budgets/summary/{id}", "GET"),
    ("/api/v1/pm/costs", "POST"),
    ("/api/v1/pm/costs/summary/{id}", "GET"),
    ("/api/v1/pm/evm/compute/{id}", "GET"),
    ("/api/v1/pm/vendors", "GET"),
    ("/api/v1/pm/vendors", "POST"),
    ("/api/v1/pm/vendors/{id}", "DELETE"),
    ("/api/v1/pm/purchase-requests", "GET"),
    ("/api/v1/pm/purchase-requests", "POST"),
    ("/api/v1/pm/purchase-requests/{id}/approve", "POST"),
]


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(pm_router, prefix="/api/v1/pm")
    return TestClient(app, raise_server_exceptions=False)


def _concrete(path: str) -> str:
    return path.replace("{id}", "probe-id")


@pytest.mark.parametrize(("path", "verb"), FINANCE_ALIAS_SITES)
def test_finance_compat_alias_resolves(client, path, verb):
    """/finance/* must resolve. 404 here is the regression."""
    r = client.request(verb, _concrete(path), follow_redirects=False)
    assert r.status_code != 404, (
        f"{verb} {path} returns 404 -- the /finance compat alias is not mounted"
    )


@pytest.mark.parametrize(("path", "verb"), CANONICAL_FINANCE_SITES)
def test_canonical_finance_paths_still_resolve(client, path, verb):
    """The aliases must not have replaced the canonical routes."""
    r = client.request(verb, _concrete(path), follow_redirects=False)
    assert r.status_code != 404, (
        f"{verb} {path} returns 404 -- a canonical route was removed"
    )


def test_alias_and_canonical_expose_the_same_verbs(client):
    """Both spellings must serve identical verbs, not a subset."""
    pairs = [
        ("/api/v1/pm/finance/budgets", "/api/v1/pm/budgets"),
        ("/api/v1/pm/finance/vendors", "/api/v1/pm/vendors"),
        ("/api/v1/pm/finance/purchase-requests", "/api/v1/pm/purchase-requests"),
    ]
    verbs = ("GET", "POST", "PUT", "PATCH", "DELETE")
    for alias, canonical in pairs:
        alias_verbs = {
            v
            for v in verbs
            if client.request(v, alias, follow_redirects=False).status_code != 404
        }
        canonical_verbs = {
            v
            for v in verbs
            if client.request(v, canonical, follow_redirects=False).status_code != 404
        }
        assert alias_verbs == canonical_verbs, (
            f"{alias} serves {sorted(alias_verbs)} but {canonical} serves "
            f"{sorted(canonical_verbs)} -- alias is incomplete"
        )


def test_finance_alias_does_not_collide_with_another_router(client):
    """Adding the alias must not shadow a pre-existing route."""
    # /finance/* belongs to the finance router only. Before the alias
    # existed this whole namespace 404'd; now every registered path
    # under it must be a finance path.
    finance_paths = {
        r.path
        for r in pm_router.routes
        if getattr(r, "path", "").startswith("/finance/")
    }
    assert finance_paths, "no /finance/* routes registered at all"
    for p in finance_paths:
        assert (
            p.startswith("/finance/budgets")
            or p.startswith("/finance/costs")
            or (p.startswith("/finance/evm"))
            or p.startswith("/finance/vendors")
            or p.startswith("/finance/purchase-requests")
            or p.startswith("/finance/timesheets")
        ), f"unexpected /finance path: {p}"
