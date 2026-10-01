"""Regression test: three macro routes were unreachable because a param route
was declared before its literal siblings.

`GET /macros/{macro_id}` was declared at macro_routes.py:103, ahead of
`GET /macros/action-types`, `GET /macros/executions` and `GET /macros/schedules`.
Starlette matches routes in declaration order, so all three literal paths were
captured by `{macro_id}` and returned the macro whose id was the literal string
"action-types" / "executions" / "schedules".

These tests are offline: they mount the real routers on a throwaway FastAPI app
and match with Starlette's own matcher. No server, no database. Unlike the rest
of tests/file_browser/, nothing here needs a live server on :8000, so these run
in CI.
"""

import importlib

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.routing import Match, Route

# (import path, attr, prefix) transcribed from app/core/routers.py
SPECS = [
    ("app.modules.file_system.routes.router", "router", "/file-system"),
    ("app.modules.file_browser", "router", ""),
    ("app.modules.file_browser.macro_routes", "router", "/file-browser"),
]


@pytest.fixture(scope="module")
def app():
    a = FastAPI()
    for mod_path, attr, prefix in SPECS:
        module = importlib.import_module(mod_path)
        a.include_router(getattr(module, attr), prefix=prefix)
    return a


def resolve(app, method, path):
    """Return the route Starlette would actually dispatch to, or None."""
    for route in app.router.routes:
        if not isinstance(route, Route):
            continue
        match, _ = route.matches(
            {
                "type": "http",
                "method": method,
                "path": path,
                "headers": [],
                "query_string": b"",
                "root_path": "",
            }
        )
        if match is Match.FULL:
            return route
    return None


SHADOWED = [
    ("GET", "/file-browser/macros/action-types", "list_action_types_handler"),
    ("GET", "/file-browser/macros/executions", "list_executions_handler"),
    ("GET", "/file-browser/macros/schedules", "list_schedules_handler"),
]


class TestMacroRouteShadowing:
    @pytest.mark.parametrize("method,path,expected", SHADOWED)
    def test_literal_route_is_reachable(self, app, method, path, expected):
        route = resolve(app, method, path)
        assert route is not None, f"{method} {path} resolves to nothing (404)"
        assert route.name == expected, (
            f"{method} {path} is captured by {route.name!r} "
            f"(declared as {route.path!r}); it must reach {expected!r}"
        )

    @pytest.mark.parametrize("method,path,expected", SHADOWED)
    def test_literal_route_not_captured_by_macro_id_param(
        self, app, method, path, expected
    ):
        """The specific failure: {macro_id} swallowing a literal sibling."""
        route = resolve(app, method, path)
        assert route is not None
        assert "{" not in route.path, (
            f"{method} {path} was matched by the param route {route.path!r}"
        )

    def test_controls_still_resolve_to_their_own_handlers(self, app):
        """Guards against 'fixing' this by deleting the literal routes."""
        controls = [
            ("/file-browser/macros/stats", "get_stats_handler"),
            ("/file-browser/macros/categories", "list_categories_handler"),
            ("/file-browser/macros", "list_macros_handler"),
        ]
        for path, expected in controls:
            route = resolve(app, "GET", path)
            assert route is not None, f"GET {path} must still resolve"
            assert route.name == expected

    def test_macro_id_param_route_still_reachable(self, app):
        """The param route must still work for a real id."""
        route = resolve(app, "GET", "/file-browser/macros/some-real-uuid")
        assert route is not None
        assert route.name == "get_macro_handler"

    def test_no_literal_get_route_is_shadowed_anywhere(self, app):
        """Generalised check across every router in scope, any depth.

        A literal path is unreachable iff a param route of the same depth, with
        a literal-compatible shape, was declared strictly earlier.
        """
        order = {}
        entries = []
        for r in app.routes:
            if not isinstance(r, APIRoute):
                continue
            for method in r.methods:
                if method in ("HEAD", "OPTIONS"):
                    continue
                order[id(r)] = len(entries)
                entries.append((method, r.path, r.name))

        groups = {}
        for i, (method, path, name) in enumerate(entries):
            segs = tuple(path.strip("/").split("/"))
            groups.setdefault((method, len(segs)), []).append((i, segs, path, name))

        unreachable = []
        for (method, _depth), items in groups.items():
            params = [x for x in items if any("{" in s for s in x[1])]
            lits = [x for x in items if not any("{" in s for s in x[1])]
            for pi, ps, pp, _pn in params:
                for li, ls, lp, ln in lits:
                    if ps == ls:
                        continue
                    if all(("{" in a) or a == b for a, b in zip(ps, ls)) and pi < li:
                        unreachable.append((method, lp, ln, pp))

        assert not unreachable, (
            "literal routes unreachable via declaration order: "
            + "; ".join(
                f"{m} {lp} ({ln}) swallowed by {pp}" for m, lp, ln, pp in unreachable
            )
        )

    def test_route_inventory_is_stable(self, app):
        """A reordering must not drop or add any endpoint."""
        count = 0
        for r in app.routes:
            if isinstance(r, APIRoute):
                count += len([m for m in r.methods if m not in ("HEAD", "OPTIONS")])
        assert count == 91, f"expected 91 (method,path) entries, got {count}"
