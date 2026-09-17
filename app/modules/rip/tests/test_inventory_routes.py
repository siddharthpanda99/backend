"""Route tests for C021 inventory endpoints (thin delegation)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.rip.routes.documents import router as documents_router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(documents_router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _flags():
    from common_lib.modules.rip.feature_flags import (
        clear_all_overrides,
        set_flag_override,
    )

    set_flag_override("NEXUS_INVENTORY_ENABLED", True)
    yield
    clear_all_overrides()


@pytest.fixture()
def _docs(monkeypatch):
    import common_lib.modules.rip.rip_documents.service as svc

    store = {
        "docA": SimpleNamespace(
            content="John arrived in London on Monday. Signed in 2022.",
            source_type="text",
        )
    }

    async def _get_doc(doc_id: str):
        return store.get(doc_id)

    monkeypatch.setattr(svc, "get_doc", _get_doc)
    return store


class TestDocumentInventoryRoute:
    def test_inventory_builds(self, client, _docs):
        resp = client.get("/rip/documents/docA/inventory")
        assert resp.status_code == 200
        inv = resp.json()["inventory"]
        assert inv["status"] == "ok"
        assert inv["doc_id"] == "docA"
        assert "Monday" in inv["dates"]

    def test_missing_doc_404(self, client, _docs):
        assert client.get("/rip/documents/nope/inventory").status_code == 404

    def test_flag_off_503(self, client, _docs):
        from common_lib.modules.rip.feature_flags import clear_all_overrides

        clear_all_overrides()
        assert client.get("/rip/documents/docA/inventory").status_code == 503


class TestCorpusInventoryRoute:
    def test_rollup(self, client, _docs):
        resp = client.get(
            "/rip/documents/corpus/inventory",
            params={"corpus_id": "c1", "doc_ids": "docA,ghost"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["corpus"]["status"] == "ok"
        assert body["corpus"]["doc_ids"] == ["docA"]
        assert body["missing_doc_ids"] == ["ghost"]

    def test_flag_off_503(self, client, _docs):
        from common_lib.modules.rip.feature_flags import clear_all_overrides

        clear_all_overrides()
        resp = client.get(
            "/rip/documents/corpus/inventory",
            params={"corpus_id": "c1", "doc_ids": "docA"},
        )
        assert resp.status_code == 503


class TestRoutesMounted:
    def test_router_has_inventory_routes(self):
        paths = {r.path for r in documents_router.routes}
        assert "/rip/documents/{document_id}/inventory" in paths
        assert "/rip/documents/corpus/inventory" in paths
