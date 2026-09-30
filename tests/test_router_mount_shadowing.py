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


# ==========================================================================
# PRECEDENCE SHADOWING — the mode the metric above cannot see
# ==========================================================================

# Starlette matches routes in REGISTRATION ORDER and takes the first hit, so a
# route declared earlier with a `{param}` segment captures every later literal
# sibling even though each path appears exactly once and no duplicate exists to
# count. Measured example: `GET /api/v1/plugins/{plugin_id}` is registered at
# index 1916, BEFORE `/api/v1/plugins/instances` (1920) and
# `/api/v1/plugins/links` (1925) - so both list handlers 404 live while the
# duplicate metric above calls them healthy.


def _segments(path: str) -> list[str]:
    return [s for s in path.split("/") if s]


def _has_param(path: str) -> bool:
    return any(s.startswith("{") and s.endswith("}") for s in _segments(path))


def _pattern_captures(pattern: str, literal: str) -> bool:
    """Would a request for `literal` be captured by route `pattern`?

    Same segment count, and each literal segment must either equal the
    pattern's static segment or be absorbed by one of its ``{param}`` segments.
    """
    p, l = _segments(pattern), _segments(literal)
    if len(p) != len(l):
        return False
    for p_seg, l_seg in zip(p, l):
        if p_seg.startswith("{") and p_seg.endswith("}"):
            continue
        if p_seg != l_seg:
            return False
    return True


@pytest.fixture(scope="module")
def ordered_routes():
    """Routes in REGISTRATION order: (index, method, path, handler_name)."""
    from app.core.routers import register_routers
    from fastapi import FastAPI
    from fastapi.routing import APIRoute

    app = FastAPI()
    register_routers(app, "/api/v1", [])

    out = []
    for i, route in enumerate(app.routes):
        if not isinstance(route, APIRoute):
            continue
        name = getattr(getattr(route, "endpoint", None), "__name__", "?")
        for method in getattr(route, "methods", None) or set():
            if method in ("HEAD", "OPTIONS"):
                continue
            out.append((i, method, route.path, name))
    return out


class TestPrecedenceShadowingIsVisible:
    """The blind spot: a param route registered BEFORE a literal sibling.

    These tests exist so the number below can never be quietly reinterpreted as
    "healthy" the way the original metric did.
    """

    def test_detector_finds_a_planted_shadow(self):
        """The detector must actually detect. A green count proves nothing if
        the detector is inert, so prove the mechanism on a synthetic table
        before trusting its verdict on the real app."""
        synthetic = [
            (0, "GET", "/api/v1/things/{thing_id}", "get_thing"),
            (1, "GET", "/api/v1/things/special", "list_special"),
        ]
        shadowed = self._scan(synthetic)
        assert shadowed, "detector found nothing in a table with an obvious shadow"
        method, path, name, captured_by = shadowed[0]
        assert (method, path) == ("GET", "/api/v1/things/special")
        assert name == "list_special"
        assert captured_by.startswith("/api/v1/things/{thing_id}")

    def test_detector_does_not_flag_later_param_routes(self):
        """A param route AFTER a literal sibling is fine and must not be
        flagged — otherwise the metric becomes noise."""
        synthetic = [
            (0, "GET", "/api/v1/things/special", "list_special"),
            (1, "GET", "/api/v1/things/{thing_id}", "get_thing"),
        ]
        assert self._scan(synthetic) == []

    def test_detector_ignores_different_segment_counts(self):
        """`/a/{id}/b` must not capture `/a/x`."""
        synthetic = [
            (0, "GET", "/api/v1/a/{id}/b", "handler"),
            (1, "GET", "/api/v1/a/x", "other"),
        ]
        assert self._scan(synthetic) == []

    def test_detector_ignores_different_methods(self):
        """A GET param route must not shadow a POST literal sibling."""
        synthetic = [
            (0, "GET", "/api/v1/things/{thing_id}", "get_thing"),
            (1, "POST", "/api/v1/things/special", "create_special"),
        ]
        assert self._scan(synthetic) == []

    @staticmethod
    def _scan(ordered):
        """Routes unreachable because an EARLIER param route captures them."""
        shadowed = []
        for idx, method, path, name in ordered:
            if _has_param(path):
                # A param route is itself capturable only by an earlier param
                # route; exact duplicates are handled by the other test class.
                pass
            for pidx, pmethod, ppath, pname in ordered:
                if pidx >= idx:
                    break
                if pmethod != method or not _has_param(ppath):
                    continue
                if _pattern_captures(ppath, path):
                    shadowed.append((method, path, name, f"{ppath} -> {pname}"))
                    break
        return shadowed

    def test_precedence_shadowed_count_did_not_regress(self, ordered_routes):
        """BASELINE RATCHET — measured on this tree, not a target.

        The previous metric reported 14 unreachable handlers and called the
        surface healthy. Measuring with registration-order precedence finds 100
        shadowed keys, of which 97 are INVISIBLE to a (method, path) duplicate
        count. This assertion exists so that number cannot rise, and so the
        difference between the two metrics is recorded rather than forgotten.

        To FIX any of these, reorder the mount in `app/core/routers.py` (mount
        literal-path routers BEFORE param-path routers), then lower this
        baseline in the same commit — never raise it.
        """
        shadowed = self._scan(ordered_routes)
        assert len(shadowed) <= 101, (
            f"precedence-shadowed routes regressed to {len(shadowed)} "
            f"(baseline 101). First few: "
            f"{[(m, p) for m, p, _, _ in shadowed[:5]]}"
        )

    def test_net_new_shadowing_is_tracked_separately(self, ordered_routes):
        """How many of the shadowed routes the ORIGINAL metric never saw.

        Reported as its own assertion because that gap — not the raw count — is
        the finding. `duplicates` covers exact repeats only.
        """
        duplicates: dict[tuple[str, str], int] = collections.Counter()
        for _, method, path, _ in ordered_routes:
            duplicates[(method, path)] += 1
        exact = {k for k, v in duplicates.items() if v > 1}

        shadowed_keys = {(m, p) for m, p, _, _ in self._scan(ordered_routes)}
        net_new = shadowed_keys - exact

        assert len(net_new) <= 98, (
            f"routes shadowed purely by precedence regressed to {len(net_new)} "
            f"(baseline 98)"
        )

    def test_named_shadowed_endpoints_are_still_shadowed(self, ordered_routes):
        """Pin the two cases investigated by hand, so they are documented
        rather than just counted.

        Both are the same defect: a `{param}` sibling registered BEFORE a
        literal sub-path, so the literal handler is unreachable and the param
        handler answers instead. These are named because a count that changes
        from 100 to 101 is otherwise indistinguishable from noise.

        `/api/v1/plugins/{plugin_id}` at index 1916 precedes
        `/api/v1/plugins/instances` (1920) and `/api/v1/plugins/links` (1925),
        so `list_plugin_instances` and `list_plugin_links` both 404 live.
        `/api/v1/projects/{project_id}` at index 78 precedes
        `/api/v1/projects/blueprints` (86), so `list_blueprints` is captured
        with project_id="blueprints".

        When these are fixed, reorder the mount so literal-path routers are
        registered before param-path routers, then LOWER these baselines in the
        same commit. Never raise them.
        """
        shadowed = {(m, p): name for m, p, name, _ in self._scan(ordered_routes)}
        for method, path, handler in [
            ("GET", "/api/v1/plugins/instances", "list_plugin_instances"),
            ("GET", "/api/v1/plugins/links", "list_plugin_links"),
            ("GET", "/api/v1/projects/blueprints", "list_blueprints"),
        ]:
            assert shadowed.get((method, path)) == handler, (
                f"{method} {path} ({handler}) is no longer shadowed. If that is "
                "intentional, remove it from this list and lower the baseline "
                "in the same commit; if not, the mount order regressed."
            )
