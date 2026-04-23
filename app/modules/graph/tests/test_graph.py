# Graph Module Tests
import pytest


class TestGraphRoutes:
    """Tests for Graph routes"""

    def test_graph_router_imports(self):
        from app.modules.graph.routes.index import router

        assert router is not None


class TestGraphNode:
    """Tests for GraphNode model"""

    def test_graph_node_has_id(self):
        from app.modules.graph.routes.index import GraphNode

        node = GraphNode(id="node1", label="Test Node", category="test")
        assert node.id == "node1"
        assert node.label == "Test Node"

    def test_graph_node_has_optional_fields(self):
        from app.modules.graph.routes.index import GraphNode

        node = GraphNode(
            id="node1", label="Test", category="test", description="desc", tags=["tag1"]
        )
        assert node.description == "desc"
        assert node.tags == ["tag1"]


class TestGraphEdge:
    """Tests for GraphEdge model"""

    def test_graph_edge_imports(self):
        from app.modules.graph.routes.index import GraphEdge

        edge = GraphEdge(source="node1", target="node2", relationship="contains")
        assert edge.source == "node1"
        assert edge.target == "node2"


class TestGraphConfig:
    """Tests for GraphConfig model"""

    def test_graph_config_imports(self):
        from app.modules.graph.routes.index import GraphConfig

        config = GraphConfig(nodes=[], edges=[])
        assert isinstance(config.nodes, list)
        assert isinstance(config.edges, list)


class TestGraphResponse:
    """Tests for GraphResponse model"""

    def test_graph_response_imports(self):
        from app.modules.graph.routes.index import GraphResponse

        response = GraphResponse(
            graph={}, nodes=[], edges=[], categories=[], summary={}
        )
        assert isinstance(response.graph, dict)
        assert isinstance(response.nodes, list)
        assert isinstance(response.edges, list)


class TestGraphEngine:
    """Tests for graph engine"""

    def test_get_engine_function_imports(self):
        from app.modules.graph.routes.index import _get_engine

        assert callable(_get_engine)


class TestGraphSerialization:
    """Tests for graph serialization"""

    def test_graph_node_json_serialization(self):
        from app.modules.graph.routes.index import GraphNode

        node = GraphNode(id="n1", label="Label", category="cat")
        json_str = node.model_dump_json()
        assert isinstance(json_str, str)
        assert "n1" in json_str
