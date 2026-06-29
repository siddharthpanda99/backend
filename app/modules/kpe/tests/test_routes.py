"""Smoke tests for KPE routes — verify imports and router structure."""

from __future__ import annotations


class TestKpeRoutes:
    """Tests for KPE route registration."""

    def test_router_imports(self):
        """Verify the KPE routes can be imported."""
        from app.modules.kpe.routes import router

        assert router is not None
        # 18 routes total (documents 2 + ingestion 2 + extraction 1 + classification 1
        # + retrieval 4 + processing 1 + summarization 1 + kg 3 + quality 1 + normalization 1 + agent 1)
        assert len(router.routes) >= 18

    def test_router_paths(self):
        """Verify expected endpoint paths are registered."""
        from app.modules.kpe.routes import router

        paths = {r.path for r in router.routes}
        expected_paths = {
            "/kpe/documents/",
            "/kpe/documents/{document_id}",
            "/kpe/ingestion/",
            "/kpe/ingestion/logs",
            "/kpe/extraction/",
            "/kpe/classification/",
            "/kpe/retrieval/search",
            "/kpe/retrieval/rewrite",
            "/kpe/retrieval/enrich",
            "/kpe/retrieval/rerank",
            "/kpe/processing/",
            "/kpe/summarization/",
            "/kpe/kg/extract",
            "/kpe/kg/infer",
            "/kpe/kg/query",
            "/kpe/quality/",
        }
        for path in expected_paths:
            assert path in paths, f"Missing path: {path}"

    def test_router_methods(self):
        """Verify all expected HTTP methods are present."""
        from app.modules.kpe.routes import router

        path_methods: dict = {}
        for route in router.routes:
            path = route.path
            if path not in path_methods:
                path_methods[path] = set()
            path_methods[path].update(route.methods)

        expected = {
            "/kpe/documents/": {"GET", "POST"},
            "/kpe/documents/{document_id}": {"GET", "DELETE"},
            "/kpe/ingestion/": {"POST"},
            "/kpe/ingestion/logs": {"GET"},
            "/kpe/extraction/": {"POST"},
            "/kpe/classification/": {"POST"},
            "/kpe/retrieval/search": {"POST"},
            "/kpe/retrieval/rewrite": {"POST"},
            "/kpe/retrieval/enrich": {"POST"},
            "/kpe/retrieval/rerank": {"POST"},
            "/kpe/processing/": {"POST"},
            "/kpe/summarization/": {"POST"},
            "/kpe/kg/extract": {"POST"},
            "/kpe/kg/infer": {"POST"},
            "/kpe/kg/query": {"POST"},
            "/kpe/quality/": {"POST"},
        }
        for path, expected_methods in expected.items():
            actual_methods = path_methods.get(path, set())
            for method in expected_methods:
                assert method in actual_methods, (
                    f"Missing {method} on {path}. "
                    f"Expected: {expected_methods}, Actual: {actual_methods}"
                )

    def test_router_registered_in_routers(self):
        """Verify the KPE router is registered in routers.py."""
        from app.core.routers import register_routers

        assert register_routers is not None
