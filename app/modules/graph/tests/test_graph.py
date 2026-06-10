# Graph Module Tests
import pytest


class TestGraphRoutes:
    """Tests for Graph routes"""

    def test_graph_router_imports(self):
        from app.modules.graph.routes.index import router

        assert router is not None

    def test_graph_service_imports(self):
        from common_lib.modules.graph import GraphService

        assert GraphService is not None
        assert callable(GraphService)


class TestGraphNode:
    """Tests for GraphNode model"""

    def test_graph_node_has_id(self):
        from common_lib.modules.graph import GraphNode

        node = GraphNode(id="node1", label="Test Node", category="test")
        assert node.id == "node1"
        assert node.label == "Test Node"

    def test_graph_node_has_optional_fields(self):
        from common_lib.modules.graph import GraphNode

        node = GraphNode(
            id="node1", label="Test", category="test", description="desc", tags=["tag1"]
        )
        assert node.description == "desc"
        assert node.tags == ["tag1"]


class TestGraphEdge:
    """Tests for GraphEdge model"""

    def test_graph_edge_imports(self):
        from common_lib.modules.graph import GraphEdge

        edge = GraphEdge(from_id="node1", to_id="node2", label="contains")
        assert edge.from_id == "node1"
        assert edge.to_id == "node2"


class TestGraphConfig:
    """Tests for GraphConfig model"""

    def test_graph_config_imports(self):
        from common_lib.modules.graph.schemas import GraphResponse

        config = GraphResponse(graph={}, nodes=[], edges=[], categories=[], summary={})
        assert isinstance(config.graph, dict)
        assert isinstance(config.nodes, list)
        assert isinstance(config.edges, list)


class TestGraphResponse:
    """Tests for GraphResponse model"""

    def test_graph_response_imports(self):
        from common_lib.modules.graph import GraphResponse

        response = GraphResponse(
            graph={}, nodes=[], edges=[], categories=[], summary={}
        )
        assert isinstance(response.graph, dict)
        assert isinstance(response.nodes, list)
        assert isinstance(response.edges, list)


class TestGraphService:
    """Tests for GraphService"""

    def test_graph_service_imports(self):
        from common_lib.modules.graph import GraphService

        svc = GraphService()
        assert svc is not None
        assert hasattr(svc, "load_graph")
        assert hasattr(svc, "invalidate_cache")


class TestGraphSerialization:
    """Tests for graph serialization"""

    def test_graph_node_json_serialization(self):
        from common_lib.modules.graph import GraphNode

        node = GraphNode(id="n1", label="Label", category="cat")
        json_str = node.model_dump_json()
        assert isinstance(json_str, str)
        assert "n1" in json_str
