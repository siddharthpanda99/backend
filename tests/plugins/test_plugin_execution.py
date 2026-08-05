"""Tests for plugin discovery, metadata, and tool execution."""

import pytest
from common_lib.modules.plugins.manager import PluginManager
from common_lib.modules.plugins.plugin import plugin
from common_lib.modules.plugins.tool import tool
from common_lib.modules.plugins.base import BaseToolPlugin
from common_lib.modules.plugins.node import node
from common_lib.modules.plugins.schemas import PluginMetadata, PluginType, HealthStatus


class TestPluginFramework:
    """Test the plugin framework fundamentals."""

    def test_plugin_decorator_sets_metadata(self):
        """@plugin decorator should attach PluginMetadata to the class."""
        @plugin(
            id="test_plugin",
            name="Test Plugin",
            description="A test plugin",
            category="testing",
            version="1.0.0",
        )
        class TestPlugin(BaseToolPlugin):
            def __init__(self):
                super().__init__()

        p = TestPlugin()
        assert p.id == "test_plugin"
        assert p.metadata.name == "Test Plugin"
        assert p.metadata.category == "testing"
        assert p.metadata.version == "1.0.0"

    def test_tool_decorator_registers_tool(self):
        """@tool decorator should mark methods as tools."""
        class TestPlugin(BaseToolPlugin):
            def __init__(self):
                meta = PluginMetadata(id="test", name="Test", category="test")
                super().__init__(meta)

            @tool(
                name="Test Tool",
                description="A test tool",
                category="test",
                audience=["planner", "executor"],
                input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
            )
            def my_tool(self, x: str = "") -> dict:
                return {"result": x}

        p = TestPlugin()
        assert hasattr(p.my_tool, "_is_plugin_tool")
        assert p.my_tool._is_plugin_tool is True
        assert p.my_tool._tool_metadata["name"] == "Test Tool"

    def test_get_nodes_discovers_tools(self):
        """get_nodes should discover all @tool-decorated methods."""
        class TestPlugin(BaseToolPlugin):
            def __init__(self):
                meta = PluginMetadata(id="test", name="Test", category="test")
                super().__init__(meta)

            @tool(name="Tool A", category="test")
            def tool_a(self) -> dict:
                return {"a": 1}

            @tool(name="Tool B", category="test")
            def tool_b(self) -> dict:
                return {"b": 2}

        p = TestPlugin()
        nodes = p.get_nodes()
        node_names = [n["name"] for n in nodes]
        assert "Tool A" in node_names
        assert "Tool B" in node_names
        assert len(nodes) == 2

    def test_get_node_handler_finds_tool(self):
        """get_node_handler should find the right method."""
        class TestPlugin(BaseToolPlugin):
            def __init__(self):
                meta = PluginMetadata(id="test", name="Test", category="test")
                super().__init__(meta)

            @tool(name="My Tool")
            def my_tool(self) -> dict:
                return {"done": True}

        p = TestPlugin()
        handler = p.get_node_handler("test.my_tool")
        assert handler is not None
        result = handler()
        assert result == {"done": True}

    def test_health_check_default(self):
        """check_health should return healthy for plugins with no required keys."""
        class TestPlugin(BaseToolPlugin):
            def __init__(self):
                meta = PluginMetadata(id="test", name="Test", category="test", required_keys=[])
                super().__init__(meta)

        p = TestPlugin()
        health = p.check_health()
        assert health.status == HealthStatus.HEALTHY

    def test_node_decorator_registers_node(self):
        """@node decorator should mark methods as nodes."""
        class TestPlugin(BaseToolPlugin):
            def __init__(self):
                meta = PluginMetadata(id="test", name="Test", category="test")
                super().__init__(meta)

            @node(
                name="Test Node",
                description="A test node",
                audience=["system"],
            )
            def my_node(self) -> dict:
                return {"node": True}

        p = TestPlugin()
        assert hasattr(p.my_node, "_is_plugin_node")
        assert p.my_node._is_plugin_node is True

    def test_plugin_manager_initializes(self):
        """PluginManager should initialize without errors."""
        manager = PluginManager()
        assert manager.engine is not None
        assert manager.extractor is not None


class TestGoogleSheetsPlugin:
    """Tests for the expanded Google Sheets plugin."""

    def test_plugin_metadata(self):
        from common_lib.modules.plugins.native.google_sheets.google_sheets_plugin import GoogleSheetsPlugin
        p = GoogleSheetsPlugin()
        assert p.id == "google_sheets"
        assert p.metadata.category == "data_storage"

    def test_all_tools_discovered(self):
        from common_lib.modules.plugins.native.google_sheets.google_sheets_plugin import GoogleSheetsPlugin
        p = GoogleSheetsPlugin()
        nodes = p.get_nodes()
        tool_names = [n["name"] for n in nodes]
        assert "Connect Google Sheets" in tool_names
        assert "Read Sheet Values" in tool_names
        assert "Write Sheet Values" in tool_names
        assert "List Spreadsheets" in tool_names
        assert "Batch Update" in tool_names
        assert len(nodes) >= 10

    def test_read_values_execution(self):
        from common_lib.modules.plugins.native.google_sheets.google_sheets_plugin import GoogleSheetsPlugin
        p = GoogleSheetsPlugin()
        result = p.read_values("test123", "Sheet1", 10)
        assert "values" in result
        assert result["range"] == "Sheet1"

    def test_batch_update_execution(self):
        from common_lib.modules.plugins.native.google_sheets.google_sheets_plugin import GoogleSheetsPlugin
        p = GoogleSheetsPlugin()
        result = p.batch_update("test123", [{"type": "update", "data": {}}])
        assert result["completed"] == 1


class TestOpenAIPlugin:
    """Tests for the expanded OpenAI plugin."""

    def test_plugin_metadata(self):
        from common_lib.modules.plugins.native.openai.openai_plugin import OpenAIPlugin
        p = OpenAIPlugin()
        assert p.id == "openai"
        assert len(p.get_nodes()) >= 8

    def test_generate_completion(self):
        from common_lib.modules.plugins.native.openai.openai_plugin import OpenAIPlugin
        p = OpenAIPlugin()
        result = p.generate_completion("Hello", model="gpt-4o")
        assert "completion" in result
        assert result["model"] == "gpt-4o"

    def test_generate_embeddings(self):
        from common_lib.modules.plugins.native.openai.openai_plugin import OpenAIPlugin
        p = OpenAIPlugin()
        result = p.generate_embeddings("test text")
        assert "embedding" in result
        assert len(result["embedding"]) > 0

    def test_list_models(self):
        from common_lib.modules.plugins.native.openai.openai_plugin import OpenAIPlugin
        p = OpenAIPlugin()
        result = p.list_models()
        assert len(result["models"]) >= 6


class TestSlackPlugin:
    """Tests for the real-HTTP Slack plugin."""

    def test_plugin_metadata(self):
        from common_lib.modules.plugins.native.slack.slack_plugin import SlackPlugin
        p = SlackPlugin()
        assert p.id == "slack"
        assert p.metadata.category == "communication"

    def test_all_tools_discovered(self):
        from common_lib.modules.plugins.native.slack.slack_plugin import SlackPlugin
        p = SlackPlugin()
        nodes = p.get_nodes()
        tool_names = [n["name"] for n in nodes]
        assert "Send Message" in tool_names
        assert "List Channels" in tool_names
        assert "List Users" in tool_names
        assert "Add Reaction" in tool_names
        assert len(nodes) >= 10

    def test_send_message_returns_dict(self):
        """send_message always returns a dict (success or error)."""
        from common_lib.modules.plugins.native.slack.slack_plugin import SlackPlugin
        p = SlackPlugin()
        result = p.send_message("#general", "Hello!")
        assert isinstance(result, dict)

    def test_send_rich_message_returns_dict(self):
        """send_rich_message always returns a dict."""
        from common_lib.modules.plugins.native.slack.slack_plugin import SlackPlugin
        p = SlackPlugin()
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}]
        result = p.send_rich_message("#general", blocks)
        assert isinstance(result, dict)

    def test_list_users_returns_dict(self):
        """list_users always returns a dict (users or error)."""
        from common_lib.modules.plugins.native.slack.slack_plugin import SlackPlugin
        p = SlackPlugin()
        result = p.list_users()
        assert isinstance(result, dict)
