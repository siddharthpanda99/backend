"""
Regression tests for router mount shadowing at the platform root.

ROUTER_DEFINITIONS mounted 44 routers at prefix "", the platform-wide
convention for top-level resources. That made `/api/v1/` itself contended:
`keys_router` and `_unified_hooks_router()` both declared a collection root
(`@router.get("/")` / `@router.get("")`), so both landed on `/api/v1/`.

FastAPI resolves a duplicate (method, path) by FIRST match, so:

    POST /api/v1/  ->  create_key      (winner)
    POST /api/v1/  ->  create_hook     (never reachable)

i.e. the platform's root endpoint silently ran the wrong handler. The same
router was also mounted twice by design: `hooks_router` at `/hooks` (correct)
and again via `_unified_hooks_router()` at `""` (the shadow).

`keys_router` is now mounted at `/keys`, matching its sibling
`credentials_router` at `/keys/credentials`. `_unified_hooks_router()` is
namespaced to `/unified-hooks` so its extra paths stay reachable without
re-contending the root.

These tests pin the outcome: no handler may be unreachable, and the specific
collection roots must resolve to the right function.
"""

import collections
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_ROUTER_MOUNT_TESTS") == "1",
    reason="router mount enumeration is expensive",
)


@pytest.fixture(scope="module")
def route_table():
    """(method, path) -> handler name, for the fully registered app."""
    from app.core.routers import register_routers
    from fastapi import FastAPI

    app = FastAPI()
    register_routers(app, "/api/v1", [])

    table: dict[tuple[str, str], str] = {}
    duplicates: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        name = getattr(getattr(route, "endpoint", None), "__name__", "")
        for method in getattr(route, "methods", None) or set():
            if method in ("HEAD", "OPTIONS"):
                continue
            key = (method, path)
            duplicates[key].append(name)
            table.setdefault(key, name)
    return table, duplicates


class TestPlatformRootIsNotContended:
    def test_root_path_has_no_shadowed_handler(self, route_table):
        """No two routers may claim `/api/v1/` itself.

        A collection root at the platform root is what caused
        `create_key` to shadow `create_hook`.
        """
        table, duplicates = route_table
        root_keys = [k for k in duplicates if k[1].rstrip("/") == "/api/v1"]
        assert root_keys == [], f"/api/v1/ is still contended: {root_keys}"

    def test_post_root_runs_the_hook_creator_or_nothing(self, route_table):
        """`POST /api/v1/` must not be `create_key`."""
        table, _ = route_table
        assert table.get(("POST", "/api/v1/")) != "create_key", (
            "POST /api/v1/ is running create_key — keys_router must not be "
            "mounted at the platform root"
        )


class TestCollectionRootsAreReachable:
    @pytest.mark.parametrize(
        ("method", "path", "expected"),
        [
            ("GET", "/api/v1/keys/", "list_keys"),
            ("POST", "/api/v1/keys/", "create_key"),
            ("GET", "/api/v1/hooks/", "list_hooks"),
            ("POST", "/api/v1/hooks/", "create_hook"),
            ("GET", "/api/v1/unified-hooks/", "list_hooks"),
            ("GET", "/api/v1/keys/credentials/", "list_credentials"),
        ],
    )
    def test_endpoint_resolves_to_its_handler(
        self, route_table, method, path, expected
    ):
        """Namespacing must not orphan a collection root."""
        table, _ = route_table
        assert table.get((method, path)) == expected, (
            f"{method} {path} no longer resolves to {expected}"
        )


class TestAgentsSubRoutersAreNotShadowed:
    """`/api/v1/agents/` was contended five ways, and swallowed its own sub-paths.

    ROUTER_DEFINITIONS mounted policy/task/profile/skill/daemon routers bare at
    `/agents` even though `agents.routes.index` already includes all five under
    their own sub-prefixes. Each declared a collection root at "/", so all five
    landed on `GET /api/v1/agents/` and first-match-wins left one reachable.
    Worse, index.py's `@router.get("/{id}")` then captured the sub-paths, so
    `GET /api/v1/agents/policies` returned 404 "Agent not found".
    """

    def test_agents_root_has_exactly_one_handler(self, route_table):
        table, duplicates = route_table
        colliders = duplicates.get(("GET", "/api/v1/agents/"), [])
        assert len(colliders) == 1, (
            f"GET /api/v1/agents/ has {len(colliders)} handlers: {colliders}"
        )

    @pytest.mark.parametrize(
        ("method", "path", "expected"),
        [
            ("GET", "/api/v1/agents/policies", "list_policies"),
            ("GET", "/api/v1/agents/tasks/", "list_tasks"),
            (
                "GET",
                "/api/v1/agents/multi-agent/executions",
                "list_multi_agent_executions",
            ),
        ],
    )
    def test_agents_subpath_resolves(self, route_table, method, path, expected):
        """These 404'd as "Agent not found" while the bare mounts existed."""
        table, _ = route_table
        assert table.get((method, path)) == expected, (
            f"{method} {path} -> {table.get((method, path))}, expected {expected}"
        )


class TestNoUnreachableHandlers:
    def test_shadowed_handler_count_did_not_regress(self, route_table):
        """Baseline after the agents fix: 14 shadowed keys / 14 unreachable.

        Was 20/24, then 17/21 after the /api/v1/ root fix. This is a ratchet,
        not a claim of zero: the remaining collisions are other modules' bare
        mounts, tracked in docs/duplication-audit/TRACK-C-ROUTES-NODES.md.
        """
        table, duplicates = route_table
        shadowed = {k: v for k, v in duplicates.items() if len(v) > 1}
        unreachable = sum(len(v) - 1 for v in shadowed.values())
        assert len(shadowed) <= 14, f"shadowed keys regressed to {len(shadowed)}"
        assert unreachable <= 14, f"unreachable handlers regressed to {unreachable}"
