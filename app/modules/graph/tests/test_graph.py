"""
API-level tests for Graph endpoints.

All routes delegate to a module-level _svc = GraphService() singleton.
We patch individual methods on _svc to test each endpoint's routing,
serialization, delegation, and error handling.

Endpoints (all under /api/v1/graph):
    GET  /                    — load_graph
    GET  /nodes               — get_nodes
    GET  /node/{node_id}      — get_node (404 if missing)
    GET  /edges               — get_edges
    GET  /search?q=           — search
    POST /clear?confirm=      — clear_graph
    POST /project             — project_knowledgebase
    GET  /stats               — get_stats
    POST /nodes               — create_node (201)
    PUT  /nodes/{node_id}     — update_node
    DELETE /nodes/{node_id}   — delete_node
    POST /edges               — create_edge (201, query params)
    DELETE /edges             — delete_edge (query params)
    GET  /shortest-path       — shortest_path (query params)
    GET  /communities         — get_communities
    GET  /export?fmt=         — export_graph

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/modules/graph/tests/test_graph.py -v
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from common_lib.modules.graph.schemas import GraphNode, GraphEdge, GraphResponse


# ── Sample data ────────────────────────────────────────────────────

SAMPLE_NODE_1 = GraphNode(
    id="n1",
    label="Node One",
    category="Knowledge",
    description="First test node",
    tags=["test", "demo"],
    entity_type="doc",
)

SAMPLE_NODE_2 = GraphNode(
    id="n2",
    label="Node Two",
    category="Knowledge",
    description="Second test node",
    tags=["test"],
    entity_type="doc",
)

SAMPLE_EDGE = GraphEdge(from_id="n1", to_id="n2", label="RELATED")

SAMPLE_GRAPH_RESPONSE = GraphResponse(
    graph={"id": "super_graph", "name": "Super Graph"},
    nodes=[SAMPLE_NODE_1, SAMPLE_NODE_2],
    edges=[SAMPLE_EDGE],
    categories=["Knowledge"],
    summary={"nodes": 2, "edges": 1},
)


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with the graph router mounted at /api/v1."""
    from app.modules.graph.routes import router as graph_router

    _app = FastAPI()
    _app.include_router(graph_router, prefix="/api/v1/graph")
    return _app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Sync TestClient for the graph app."""
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════
# GET /api/v1/graph  — Load full graph
# ═══════════════════════════════════════════════════════════════════


class TestLoadGraph:
    """GET /api/v1/graph — load the full graph."""

    MODULE = "app.modules.graph.routes.index._svc"

    def test_load_graph_returns_graph_response(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc as graph_svc

        original = graph_svc.load_graph
        graph_svc.load_graph = AsyncMock(return_value=SAMPLE_GRAPH_RESPONSE)  # type: ignore[method-assign]
        try:
            response = client.get("/api/v1/graph")
            assert response.status_code == 200
            body = response.json()
            assert body["graph"]["id"] == "super_graph"
            assert len(body["nodes"]) == 2
            assert len(body["edges"]) == 1
            assert "Knowledge" in body["categories"]
            assert body["summary"]["nodes"] == 2
        finally:
            graph_svc.load_graph = original  # type: ignore[method-assign]

    def test_load_graph_with_refresh(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc as graph_svc

        original = graph_svc.load_graph
        mock_load = AsyncMock(return_value=SAMPLE_GRAPH_RESPONSE)
        graph_svc.load_graph = mock_load  # type: ignore[method-assign]
        try:
            client.get("/api/v1/graph?refresh=true")
            mock_load.assert_called_once_with(True)
        finally:
            graph_svc.load_graph = original  # type: ignore[method-assign]

    def test_load_graph_nodes_have_required_fields(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.load_graph
        mock_load = AsyncMock(return_value=SAMPLE_GRAPH_RESPONSE)
        _svc.load_graph = mock_load  # type: ignore[method-assign]
        try:
            response = client.get("/api/v1/graph")
            node = response.json()["nodes"][0]
            assert "id" in node
            assert "label" in node
            assert "category" in node
        finally:
            _svc.load_graph = original  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════
# GET /api/v1/graph/nodes  — List all nodes
# ═══════════════════════════════════════════════════════════════════


class TestGetNodes:
    """GET /api/v1/graph/nodes — list all nodes."""

    def test_get_nodes_returns_list(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.get_nodes
        _svc.get_nodes = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "nodes": [SAMPLE_NODE_1.model_dump(), SAMPLE_NODE_2.model_dump()],
                "categories": ["Knowledge"],
            }
        )
        try:
            response = client.get("/api/v1/graph/nodes")
            assert response.status_code == 200
            body = response.json()
            assert len(body["nodes"]) == 2
            assert body["nodes"][0]["id"] == "n1"
            assert body["categories"] == ["Knowledge"]
        finally:
            _svc.get_nodes = original  # type: ignore[method-assign]

    def test_get_nodes_empty(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.get_nodes
        _svc.get_nodes = AsyncMock(  # type: ignore[method-assign]
            return_value={"nodes": [], "categories": []}
        )
        try:
            response = client.get("/api/v1/graph/nodes")
            assert response.status_code == 200
            assert response.json()["nodes"] == []
        finally:
            _svc.get_nodes = original  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════
# GET /api/v1/graph/node/{node_id}  — Get single node
# ═══════════════════════════════════════════════════════════════════


class TestGetNode:
    """GET /api/v1/graph/node/{node_id} — get a single node."""

    def test_get_node_returns_node(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.get_node
        _svc.get_node = AsyncMock(return_value=SAMPLE_NODE_1)  # type: ignore[method-assign]
        try:
            response = client.get("/api/v1/graph/node/n1")
            assert response.status_code == 200
            body = response.json()
            assert body["id"] == "n1"
            assert body["label"] == "Node One"
            assert body["category"] == "Knowledge"
        finally:
            _svc.get_node = original  # type: ignore[method-assign]

    def test_get_node_not_found(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.get_node
        _svc.get_node = AsyncMock(  # type: ignore[method-assign]
            side_effect=HTTPException(status_code=404, detail="Node nonexistent not found")
        )
        try:
            response = client.get("/api/v1/graph/node/nonexistent")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            _svc.get_node = original  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════
# GET /api/v1/graph/edges  — List all edges
# ═══════════════════════════════════════════════════════════════════


class TestGetEdges:
    """GET /api/v1/graph/edges — list all edges."""

    def test_get_edges_returns_list(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.get_edges
        _svc.get_edges = AsyncMock(return_value=[SAMPLE_EDGE])  # type: ignore[method-assign]
        try:
            response = client.get("/api/v1/graph/edges")
            assert response.status_code == 200
            body = response.json()
            assert isinstance(body, list)
            assert body[0]["from_id"] == "n1"
            assert body[0]["to_id"] == "n2"
        finally:
            _svc.get_edges = original  # type: ignore[method-assign]

    def test_get_edges_empty(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.get_edges
        _svc.get_edges = AsyncMock(return_value=[])  # type: ignore[method-assign]
        try:
            response = client.get("/api/v1/graph/edges")
            assert response.status_code == 200
            assert response.json() == []
        finally:
            _svc.get_edges = original  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════
# GET /api/v1/graph/search  — Search nodes
# ═══════════════════════════════════════════════════════════════════


class TestSearchGraph:
    """GET /api/v1/graph/search — search nodes by query."""

    def test_search_returns_results(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.search
        _svc.search = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "results": [SAMPLE_NODE_1.model_dump()],
                "query": "Node One",
                "count": 1,
            }
        )
        try:
            response = client.get("/api/v1/graph/search?q=Node+One")
            assert response.status_code == 200
            body = response.json()
            assert body["count"] == 1
            assert body["results"][0]["id"] == "n1"
        finally:
            _svc.search = original  # type: ignore[method-assign]

    def test_search_empty_query(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.search
        _svc.search = AsyncMock(  # type: ignore[method-assign]
            return_value={"results": [], "query": "", "count": 0}
        )
        try:
            response = client.get("/api/v1/graph/search")
            assert response.status_code == 200
            assert response.json()["results"] == []
        finally:
            _svc.search = original  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════
# POST /api/v1/graph/clear  — Clear graph
# ═══════════════════════════════════════════════════════════════════


class TestClearGraph:
    """POST /api/v1/graph/clear — clear the graph."""

    def test_clear_without_confirm_returns_skipped(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.clear_graph
        _svc.clear_graph = AsyncMock(  # type: ignore[method-assign]
            return_value={"status": "skipped", "message": "Set confirm=true to clear the graph"}
        )
        try:
            response = client.post("/api/v1/graph/clear?confirm=false")
            assert response.status_code == 200
            assert response.json()["status"] == "skipped"
        finally:
            _svc.clear_graph = original  # type: ignore[method-assign]

    def test_clear_with_confirm(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.clear_graph
        _svc.clear_graph = AsyncMock(  # type: ignore[method-assign]
            return_value={"status": "cleared", "message": "Graph super_graph dropped"}
        )
        try:
            response = client.post("/api/v1/graph/clear?confirm=true")
            assert response.status_code == 200
            assert response.json()["status"] == "cleared"
        finally:
            _svc.clear_graph = original  # type: ignore[method-assign]

    def test_clear_delegates_confirm_param(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc as graph_svc

        original = graph_svc.clear_graph
        mock_clear = AsyncMock(
            return_value={"status": "cleared", "message": "Done"}
        )
        graph_svc.clear_graph = mock_clear  # type: ignore[method-assign]
        try:
            client.post("/api/v1/graph/clear?confirm=true")
            mock_clear.assert_called_once_with(True)
        finally:
            graph_svc.clear_graph = original  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════
# POST /api/v1/graph/project  — Project knowledgebase
# ═══════════════════════════════════════════════════════════════════


class TestProjectGraph:
    """POST /api/v1/graph/project — project knowledgebase to graph."""

    def test_project_returns_summary(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.project_knowledgebase
        _svc.project_knowledgebase = AsyncMock(  # type: ignore[method-assign]
            return_value={"status": "projected", "nodes": 5, "edges": 3}
        )
        try:
            response = client.post("/api/v1/graph/project")
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "projected"
            assert body["nodes"] == 5
        finally:
            _svc.project_knowledgebase = original  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════
# GET /api/v1/graph/stats  — Graph statistics
# ═══════════════════════════════════════════════════════════════════


class TestGraphStats:
    """GET /api/v1/graph/stats — graph statistics."""

    def test_stats_returns_counts(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.get_stats
        _svc.get_stats = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "total_nodes": 10,
                "total_edges": 5,
                "by_type": {"doc": 8, "entity": 2},
                "categories": ["Knowledge"],
            }
        )
        try:
            response = client.get("/api/v1/graph/stats")
            assert response.status_code == 200
            body = response.json()
            assert body["total_nodes"] == 10
            assert body["total_edges"] == 5
        finally:
            _svc.get_stats = original  # type: ignore[method-assign]

    def test_stats_empty(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.get_stats
        _svc.get_stats = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "total_nodes": 0,
                "total_edges": 0,
                "by_type": {},
                "categories": [],
            }
        )
        try:
            response = client.get("/api/v1/graph/stats")
            assert response.status_code == 200
            assert response.json()["total_nodes"] == 0
        finally:
            _svc.get_stats = original  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════
# POST /api/v1/graph/nodes  — Create node (201)
# ═══════════════════════════════════════════════════════════════════


class TestCreateNode:
    """POST /api/v1/graph/nodes — create a node (status 201)."""

    def test_create_node_returns_201(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.create_node
        _svc.create_node = AsyncMock(return_value=SAMPLE_NODE_1)  # type: ignore[method-assign]
        try:
            response = client.post(
                "/api/v1/graph/nodes",
                json={"id": "n1", "label": "Node One", "category": "Knowledge"},
            )
            assert response.status_code == 201
            body = response.json()
            assert body["id"] == "n1"
            assert body["label"] == "Node One"
        finally:
            _svc.create_node = original  # type: ignore[method-assign]

    def test_create_node_includes_all_fields(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc as graph_svc

        # Return a node matching the input so assertions pass
        expected = GraphNode(
            id="n1", label="Node One", category="Knowledge",
            description="desc", tags=["a", "b"], entity_type="doc",
        )
        original = graph_svc.create_node
        graph_svc.create_node = AsyncMock(return_value=expected)  # type: ignore[method-assign]
        try:
            response = client.post(
                "/api/v1/graph/nodes",
                json={
                    "id": "n1", "label": "Node One", "category": "Knowledge",
                    "description": "desc", "tags": ["a", "b"], "entity_type": "doc",
                },
            )
            assert response.status_code == 201
            body = response.json()
            assert body["description"] == "desc"
            assert body["tags"] == ["a", "b"]
        finally:
            graph_svc.create_node = original  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════
# PUT /api/v1/graph/nodes/{node_id}  — Update node
# ═══════════════════════════════════════════════════════════════════


class TestUpdateNode:
    """PUT /api/v1/graph/nodes/{node_id} — update a node."""

    def test_update_node_returns_updated(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        updated = GraphNode(id="n1", label="Updated Label", category="Knowledge")
        original = _svc.update_node
        _svc.update_node = AsyncMock(return_value=updated)  # type: ignore[method-assign]
        try:
            response = client.put(
                "/api/v1/graph/nodes/n1",
                json={"label": "Updated Label"},
            )
            assert response.status_code == 200
            assert response.json()["label"] == "Updated Label"
        finally:
            _svc.update_node = original  # type: ignore[method-assign]

    def test_update_node_delegates(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.update_node
        mock_update = AsyncMock(
            return_value=GraphNode(id="n1", label="Updated", category="Knowledge")
        )
        _svc.update_node = mock_update  # type: ignore[method-assign]
        try:
            client.put("/api/v1/graph/nodes/n1", json={"label": "Updated"})
            mock_update.assert_called_once_with("n1", {"label": "Updated"})
        finally:
            _svc.update_node = original  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════
# DELETE /api/v1/graph/nodes/{node_id}  — Delete node
# ═══════════════════════════════════════════════════════════════════


class TestDeleteNode:
    """DELETE /api/v1/graph/nodes/{node_id} — delete a node."""

    def test_delete_node_returns_status(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.delete_node
        _svc.delete_node = AsyncMock(  # type: ignore[method-assign]
            return_value={"status": "deleted", "node_id": "n1"}
        )
        try:
            response = client.delete("/api/v1/graph/nodes/n1")
            assert response.status_code == 200
            assert response.json()["status"] == "deleted"
        finally:
            _svc.delete_node = original  # type: ignore[method-assign]

    def test_delete_node_delegates(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.delete_node
        mock_delete = AsyncMock(
            return_value={"status": "deleted", "node_id": "n1"}
        )
        _svc.delete_node = mock_delete  # type: ignore[method-assign]
        try:
            client.delete("/api/v1/graph/nodes/n1")
            mock_delete.assert_called_once_with("n1")
        finally:
            _svc.delete_node = original  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════
# POST /api/v1/graph/edges  — Create edge (201, query params)
# ═══════════════════════════════════════════════════════════════════


class TestCreateEdge:
    """POST /api/v1/graph/edges — create an edge (status 201)."""

    def test_create_edge_returns_201(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.create_edge
        _svc.create_edge = AsyncMock(return_value=SAMPLE_EDGE)  # type: ignore[method-assign]
        try:
            response = client.post("/api/v1/graph/edges?from_id=n1&to_id=n2&label=RELATED")
            assert response.status_code == 201
            body = response.json()
            assert body["from_id"] == "n1"
            assert body["to_id"] == "n2"
            assert body["label"] == "RELATED"
        finally:
            _svc.create_edge = original  # type: ignore[method-assign]

    def test_create_edge_default_label(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc as graph_svc

        original = graph_svc.create_edge
        mock_create = AsyncMock(return_value=SAMPLE_EDGE)
        graph_svc.create_edge = mock_create  # type: ignore[method-assign]
        try:
            client.post("/api/v1/graph/edges?from_id=n1&to_id=n2")
            # Route passes from_id, to_id, label as positional args
            args, _ = mock_create.call_args
            assert len(args) >= 3
            assert args[2] == "RELATED"
        finally:
            graph_svc.create_edge = original  # type: ignore[method-assign]

    def test_create_edge_requires_from_and_to(self, client: TestClient) -> None:
        response = client.post("/api/v1/graph/edges?from_id=n1")
        assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# DELETE /api/v1/graph/edges  — Delete edge (query params)
# ═══════════════════════════════════════════════════════════════════


class TestDeleteEdge:
    """DELETE /api/v1/graph/edges — delete an edge."""

    def test_delete_edge_returns_status(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.delete_edge
        _svc.delete_edge = AsyncMock(  # type: ignore[method-assign]
            return_value={"status": "deleted", "from": "n1", "to": "n2", "label": "RELATED"}
        )
        try:
            response = client.delete("/api/v1/graph/edges?from_id=n1&to_id=n2")
            assert response.status_code == 200
            assert response.json()["status"] == "deleted"
        finally:
            _svc.delete_edge = original  # type: ignore[method-assign]

    def test_delete_edge_delegates(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.delete_edge
        mock_delete = AsyncMock(
            return_value={"status": "deleted", "from": "n1", "to": "n2", "label": "RELATED"}
        )
        _svc.delete_edge = mock_delete  # type: ignore[method-assign]
        try:
            client.delete("/api/v1/graph/edges?from_id=n1&to_id=n2")
            mock_delete.assert_called_once_with("n1", "n2", "RELATED")
        finally:
            _svc.delete_edge = original  # type: ignore[method-assign]

    def test_delete_edge_requires_from_and_to(self, client: TestClient) -> None:
        response = client.delete("/api/v1/graph/edges?from_id=n1")
        assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# GET /api/v1/graph/shortest-path  — Shortest path
# ═══════════════════════════════════════════════════════════════════


class TestShortestPath:
    """GET /api/v1/graph/shortest-path — shortest path between nodes."""

    def test_shortest_path_found(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.shortest_path
        _svc.shortest_path = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "found": True,
                "path_length": 1,
                "nodes": [{"id": "n1"}, {"id": "n2"}],
                "edges": [{"from": "n1", "to": "n2"}],
            }
        )
        try:
            response = client.get("/api/v1/graph/shortest-path?from_id=n1&to_id=n2")
            assert response.status_code == 200
            body = response.json()
            assert body["found"] is True
            assert body["path_length"] == 1
        finally:
            _svc.shortest_path = original  # type: ignore[method-assign]

    def test_shortest_path_not_found(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.shortest_path
        _svc.shortest_path = AsyncMock(  # type: ignore[method-assign]
            return_value={"found": False, "path_length": 0, "nodes": [], "edges": []}
        )
        try:
            response = client.get("/api/v1/graph/shortest-path?from_id=n1&to_id=n3")
            assert response.status_code == 200
            assert response.json()["found"] is False
        finally:
            _svc.shortest_path = original  # type: ignore[method-assign]

    def test_shortest_path_delegates_params(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.shortest_path
        mock_path = AsyncMock(
            return_value={"found": False, "path_length": 0, "nodes": [], "edges": []}
        )
        _svc.shortest_path = mock_path  # type: ignore[method-assign]
        try:
            client.get("/api/v1/graph/shortest-path?from_id=a&to_id=b&max_depth=10")
            mock_path.assert_called_once_with("a", "b", 10)
        finally:
            _svc.shortest_path = original  # type: ignore[method-assign]

    def test_shortest_path_requires_from_and_to(self, client: TestClient) -> None:
        response = client.get("/api/v1/graph/shortest-path?from_id=a")
        assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# GET /api/v1/graph/communities  — Community detection
# ═══════════════════════════════════════════════════════════════════


class TestCommunities:
    """GET /api/v1/graph/communities — detect communities."""

    def test_communities_returns_list(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.get_communities
        _svc.get_communities = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "total_communities": 2,
                "communities": [
                    {"id": "knowledge", "name": "Knowledge", "members": [], "size": 5},
                    {"id": "entities", "name": "Entities", "members": [], "size": 3},
                ],
                "algorithm": "category_grouping",
            }
        )
        try:
            response = client.get("/api/v1/graph/communities")
            assert response.status_code == 200
            body = response.json()
            assert body["total_communities"] == 2
            assert len(body["communities"]) == 2
        finally:
            _svc.get_communities = original  # type: ignore[method-assign]

    def test_communities_empty(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.get_communities
        _svc.get_communities = AsyncMock(  # type: ignore[method-assign]
            return_value={"total_communities": 0, "communities": [], "algorithm": "category_grouping"}
        )
        try:
            response = client.get("/api/v1/graph/communities")
            assert response.status_code == 200
            assert response.json()["communities"] == []
        finally:
            _svc.get_communities = original  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════
# GET /api/v1/graph/export  — Export graph
# ═══════════════════════════════════════════════════════════════════


class TestExportGraph:
    """GET /api/v1/graph/export — export the graph."""

    def test_export_json(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.export_graph
        _svc.export_graph = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "format": "json",
                "graph": SAMPLE_GRAPH_RESPONSE.model_dump(),
            }
        )
        try:
            response = client.get("/api/v1/graph/export?fmt=json")
            assert response.status_code == 200
            body = response.json()
            assert body["format"] == "json"
            assert "graph" in body
        finally:
            _svc.export_graph = original  # type: ignore[method-assign]

    def test_export_cypher(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.export_graph
        _svc.export_graph = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "format": "cypher",
                "statements": [
                    "MERGE (n:Node {id: 'n1', name: 'Node One', category: 'Knowledge'});",
                ],
                "count": 1,
            }
        )
        try:
            response = client.get("/api/v1/graph/export?fmt=cypher")
            assert response.status_code == 200
            body = response.json()
            assert body["format"] == "cypher"
            assert len(body["statements"]) == 1
        finally:
            _svc.export_graph = original  # type: ignore[method-assign]

    def test_export_default_format(self, client: TestClient) -> None:
        from app.modules.graph.routes.index import _svc

        original = _svc.export_graph
        mock_export = AsyncMock(
            return_value={"format": "json", "graph": {}}
        )
        _svc.export_graph = mock_export  # type: ignore[method-assign]
        try:
            client.get("/api/v1/graph/export")
            mock_export.assert_called_once_with("json")
        finally:
            _svc.export_graph = original  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════
# Routing integrity
# ═══════════════════════════════════════════════════════════════════


class TestGraphRoutingIntegrity:
    """Verify all graph routes are registered at expected paths."""

    def test_all_graph_routes_in_openapi(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})

        assert "/api/v1/graph/" in paths
        assert "/api/v1/graph/nodes" in paths
        assert "/api/v1/graph/node/{node_id}" in paths
        assert "/api/v1/graph/edges" in paths
        assert "/api/v1/graph/search" in paths
        assert "/api/v1/graph/clear" in paths
        assert "/api/v1/graph/project" in paths
        assert "/api/v1/graph/stats" in paths
        assert "/api/v1/graph/shortest-path" in paths
        assert "/api/v1/graph/communities" in paths
        assert "/api/v1/graph/export" in paths

    def test_graph_routes_have_correct_methods(self, client: TestClient) -> None:
        paths = client.get("/openapi.json").json().get("paths", {})

        assert "get" in paths["/api/v1/graph/"]
        assert "get" in paths["/api/v1/graph/nodes"]
        assert "get" in paths["/api/v1/graph/node/{node_id}"]
        assert "get" in paths["/api/v1/graph/edges"]
        assert "get" in paths["/api/v1/graph/search"]
        assert "post" in paths["/api/v1/graph/clear"]
        assert "post" in paths["/api/v1/graph/project"]
        assert "get" in paths["/api/v1/graph/stats"]
        assert "post" in paths["/api/v1/graph/nodes"]
        # PUT/DELETE for nodes uses /nodes/{node_id} (not /node/{node_id})
        assert "put" in paths["/api/v1/graph/nodes/{node_id}"]
        assert "delete" in paths["/api/v1/graph/nodes/{node_id}"]
        assert "post" in paths["/api/v1/graph/edges"]
        assert "delete" in paths["/api/v1/graph/edges"]
        assert "get" in paths["/api/v1/graph/shortest-path"]
        assert "get" in paths["/api/v1/graph/communities"]
        assert "get" in paths["/api/v1/graph/export"]
