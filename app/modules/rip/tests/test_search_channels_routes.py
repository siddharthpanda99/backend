"""Route tests for C028 channel endpoints (thin delegation, stateless)."""

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


DOCS = {
    "docA": "John arrived in London on Monday. The agreement was signed in 2022.",
    "docB": "I saw John arrive on Tuesday. He carried a black suitcase.",
}


def _inventories():
    from common_lib.modules.rip.rip_documents.inventory import (
        build_document_inventory,
    )

    return [build_document_inventory(d, t)["inventory"] for d, t in DOCS.items()]


class TestChannelSearch:
    def test_explicit_channels(self, client):
        resp = client.post(
            "/rip/search/channels",
            json={
                "query": "John Monday",
                "query_types": ["ENTITY_LOOKUP"],
                "channels": ["lexical", "entity"],
                "documents": DOCS,
                "inventories": _inventories(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["channels"] == ["lexical", "entity"]
        assert "lexical" in body["results"]

    def test_plan_selects_channels(self, client):
        resp = client.post(
            "/rip/search/channels",
            json={
                "query": "When did John arrive?",
                "documents": DOCS,
                "inventories": _inventories(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "TIMELINE" in body["plan_query_types"]
        assert "temporal" in body["channels"]

    def test_flag_off_503(self, client):
        from common_lib.modules.rip.feature_flags import clear_all_overrides

        clear_all_overrides()
        resp = client.post("/rip/search/channels", json={"query": "x"})
        assert resp.status_code == 503

    def test_empty_query_422(self, client):
        assert (
            client.post("/rip/search/channels", json={"query": ""}).status_code == 422
        )


class TestEntityEventRoutes:
    def test_entity_channel(self, client):
        resp = client.post(
            "/rip/graph/entity-channel",
            json={"query": "Where did John arrive?", "inventories": _inventories()},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["mentions"]

    def test_event_channel(self, client):
        resp = client.post(
            "/rip/graph/event-channel",
            json={"query": "When did John arrive?", "inventories": _inventories()},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["events"]

    def test_flag_off_503(self, client):
        from common_lib.modules.rip.feature_flags import clear_all_overrides

        clear_all_overrides()
        assert (
            client.post("/rip/graph/entity-channel", json={"query": "x"}).status_code
            == 503
        )


class TestRoutesMounted:
    def test_paths(self):
        paths = {r.path for r in search_router.routes} | {
            r.path for r in graph_router.routes
        }
        assert "/rip/search/channels" in paths
        assert "/rip/graph/entity-channel" in paths
        assert "/rip/graph/event-channel" in paths
