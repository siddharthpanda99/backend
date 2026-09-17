"""Route tests for C028 ext: channel params + structural/exhaustive/mode routes.

Additive-only contract under test:
- Legacy search/graph endpoints WITHOUT `channels` behave exactly as before
  (no flag gate on the default path — flag-off still 200).
- WITH valid `channels` → 200; unknown → 400; flag-off + channels → 503.
- New thin endpoints delegate to the C023/C025/C026 surfaces (503 off).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.rip.routes.search import router as search_router
from app.modules.rip.routes.graph import router as graph_router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(search_router)
    app.include_router(graph_router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _flags():
    from common_lib.modules.rip.feature_flags import (
        clear_all_overrides,
        set_flag_override,
    )

    set_flag_override("NEXUS_RETRIEVAL_CHANNELS_ENABLED", True)
    set_flag_override("NEXUS_QUERY_PLANNING_ENABLED", True)
    set_flag_override("NEXUS_INVENTORY_ENABLED", True)
    yield
    clear_all_overrides()


@pytest.fixture()
def _stubs(monkeypatch):
    import common_lib.modules.rip.rip_retrieval.service as retrieval_svc
    import common_lib.modules.rip.rip_graph.service as graph_svc

    async def _empty_list(**kwargs):
        return []

    async def _empty_graph(**kwargs):
        return {"nodes": [], "edges": []}

    monkeypatch.setattr(retrieval_svc, "hybrid_search", _empty_list)
    monkeypatch.setattr(retrieval_svc, "bm25_search", _empty_list)
    monkeypatch.setattr(retrieval_svc, "sparse_search", _empty_list)
    monkeypatch.setattr(graph_svc, "search_graph", _empty_graph)


DOCS = {
    "docA": "John arrived in London on Monday. The agreement was signed in 2022.",
    "docB": "I saw John arrive on Tuesday. He carried a black suitcase.",
}

CHUNKS = [
    {
        "chunk_id": "c1",
        "doc_id": "docA",
        "content": "John arrived in London on Monday",
        "page": 1,
        "section": "intro",
        "entities": [{"text": "John"}, {"text": "London"}],
        "claims": [{"text": "John arrived in London on Monday"}],
        "dates": ["Monday"],
        "events": [],
        "prev_id": None,
        "next_id": "c2",
    },
    {
        "chunk_id": "c2",
        "doc_id": "docA",
        "content": "The agreement was signed in 2022",
        "page": 1,
        "section": "intro",
        "entities": [],
        "claims": [],
        "dates": ["2022"],
        "events": [],
        "prev_id": "c1",
        "next_id": None,
    },
]


def _inventories():
    from common_lib.modules.rip.rip_documents.inventory import (
        build_document_inventory,
    )

    return [build_document_inventory(d, t)["inventory"] for d, t in DOCS.items()]


class TestLegacyChannelParams:
    def test_unified_default_behavior_unchanged(self, client, _stubs):
        resp = client.post("/rip/search", json={"query": "John Monday"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "John Monday"
        assert body["retrievers_used"] == ["bm25", "dense"]
        assert body["total_results"] == 0

    def test_unified_valid_channels_accepted(self, client, _stubs):
        resp = client.post(
            "/rip/search",
            params={"channels": "lexical,entity"},
            json={"query": "John Monday"},
        )
        assert resp.status_code == 200

    def test_unified_invalid_channels_400(self, client, _stubs):
        resp = client.post(
            "/rip/search",
            params={"channels": "bogus"},
            json={"query": "John Monday"},
        )
        assert resp.status_code == 400

    def test_unified_channels_flag_off_503(self, client, _stubs):
        from common_lib.modules.rip.feature_flags import clear_all_overrides

        clear_all_overrides()
        resp = client.post(
            "/rip/search",
            params={"channels": "lexical"},
            json={"query": "John Monday"},
        )
        assert resp.status_code == 503

    def test_unified_absent_channels_flag_off_still_200(self, client, _stubs):
        """Default path is ungated: flag-off without channels still works."""
        from common_lib.modules.rip.feature_flags import clear_all_overrides

        clear_all_overrides()
        resp = client.post("/rip/search", json={"query": "John Monday"})
        assert resp.status_code == 200

    def test_bm25_channels_mirrored(self, client, _stubs):
        assert (
            client.post(
                "/rip/search/bm25",
                params={"channels": "lexical"},
                json={"query": "John"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/rip/search/bm25",
                params={"channels": "nope"},
                json={"query": "John"},
            ).status_code
            == 400
        )

    def test_graph_search_channels_param(self, client, _stubs):
        assert (
            client.post("/rip/graph/search", json={"query": "John"}).status_code == 200
        )
        assert (
            client.post(
                "/rip/graph/search",
                params={"channels": "graph,entity"},
                json={"query": "John"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/rip/graph/search",
                params={"channels": "nope"},
                json={"query": "John"},
            ).status_code
            == 400
        )

    def test_graph_search_channels_flag_off_503(self, client, _stubs):
        from common_lib.modules.rip.feature_flags import clear_all_overrides

        clear_all_overrides()
        assert (
            client.post(
                "/rip/graph/search",
                params={"channels": "graph"},
                json={"query": "John"},
            ).status_code
            == 503
        )


class TestGapEndpoints:
    def test_structural(self, client):
        resp = client.post(
            "/rip/search/structural",
            json={
                "query": "John Monday",
                "chunks": CHUNKS,
                "query_types": ["ENTITY_LOOKUP"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["hits"]

    def test_structural_flag_off_503(self, client):
        from common_lib.modules.rip.feature_flags import clear_all_overrides

        clear_all_overrides()
        assert (
            client.post(
                "/rip/search/structural",
                json={"query": "John", "chunks": CHUNKS},
            ).status_code
            == 503
        )

    def test_exhaustive(self, client):
        resp = client.post(
            "/rip/search/exhaustive",
            json={"query": "John", "inventories": _inventories()},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["handoff"]["status"] == "ok"
        assert body["occurrences"]

    def test_exhaustive_flag_off_503(self, client):
        from common_lib.modules.rip.feature_flags import clear_all_overrides

        clear_all_overrides()
        assert (
            client.post(
                "/rip/search/exhaustive",
                json={"query": "John", "inventories": _inventories()},
            ).status_code
            == 503
        )

    def test_mode_explicit_local(self, client):
        resp = client.post(
            "/rip/search/mode",
            json={
                "query": "John Monday",
                "mode": "LOCAL",
                "documents": DOCS,
                "inventories": _inventories(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "LOCAL"
        assert body["status"] == "ok"

    def test_mode_plan_chosen(self, client):
        resp = client.post(
            "/rip/search/mode",
            json={
                "query": "When did John arrive?",
                "documents": DOCS,
                "inventories": _inventories(),
            },
        )
        assert resp.status_code == 200
        assert resp.json()["mode"] in {"LOCAL", "GLOBAL", "HYBRID", "ADAPTIVE"}

    def test_mode_invalid_400(self, client):
        assert (
            client.post(
                "/rip/search/mode", json={"query": "x", "mode": "SIDEWAYS"}
            ).status_code
            == 400
        )

    def test_mode_flag_off_503(self, client):
        from common_lib.modules.rip.feature_flags import clear_all_overrides

        clear_all_overrides()
        assert (
            client.post(
                "/rip/search/mode", json={"query": "x", "mode": "LOCAL"}
            ).status_code
            == 503
        )


class TestRoutesMounted:
    def test_paths(self):
        paths = {r.path for r in search_router.routes} | {
            r.path for r in graph_router.routes
        }
        assert "/rip/search/structural" in paths
        assert "/rip/search/exhaustive" in paths
        assert "/rip/search/mode" in paths
        # pre-existing endpoints untouched
        assert "/rip/search/channels" in paths
        assert "/rip/graph/entity-channel" in paths
        assert "/rip/graph/event-channel" in paths
