"""Tests for GitLab plugin."""

import pytest
from typing import Dict, Any
from common_lib.modules.plugins.native.gitlab.gitlab_plugin import GitLabPlugin


class TestGitLabPlugin:
    """Test GitLab plugin metadata, tool discovery, and non-HTTP methods."""

    def test_plugin_metadata(self):
        p = GitLabPlugin()
        assert p.id == "gitlab"
        assert p.metadata.category == "dev_tools"
        assert p.metadata.version == "2.0.0"
        assert "python-gitlab" in p.metadata.dependencies

    def test_all_tools_discovered(self):
        p = GitLabPlugin()
        nodes = p.get_nodes()
        tool_names = {n["name"] for n in nodes}
        assert "Connect GitLab" in tool_names
        assert "List Projects" in tool_names
        assert "List Merge Requests" in tool_names
        assert "List Pipelines" in tool_names
        assert "Search Code" in tool_names
        assert "Raw API Request" in tool_names
        assert len(nodes) >= 15

    def test_batch_operation(self):
        """batch_operation does not use HTTP — returns mock data directly."""
        p = GitLabPlugin()
        result = p.batch_operation([{"action": "test"}])
        assert result["completed"] == 1

    def test_has_http_mixin(self):
        """Plugin should have HttpPluginMixin methods available."""
        p = GitLabPlugin()
        assert hasattr(p, "_request")
        assert hasattr(p, "_get")
        assert hasattr(p, "_post")


class TestConfluencePlugin:
    """Test Confluence plugin."""

    def test_metadata(self):
        from common_lib.modules.plugins.native.confluence.confluence_plugin import ConfluencePlugin
        p = ConfluencePlugin()
        assert p.id == "confluence"
        assert len(p.get_nodes()) >= 10


class TestAsanaPlugin:
    """Test Asana plugin."""

    def test_metadata(self):
        from common_lib.modules.plugins.native.asana.asana_plugin import AsanaPlugin
        p = AsanaPlugin()
        assert p.id == "asana"
        assert len(p.get_nodes()) >= 10


class TestLinearPlugin:
    """Test Linear plugin."""

    def test_metadata(self):
        from common_lib.modules.plugins.native.linear.linear_plugin import LinearPlugin
        p = LinearPlugin()
        assert p.id == "linear"
        assert len(p.get_nodes()) >= 10


class TestMattermostPlugin:
    """Test Mattermost plugin."""

    def test_metadata(self):
        from common_lib.modules.plugins.native.mattermost.mattermost_plugin import MattermostPlugin
        p = MattermostPlugin()
        assert p.id == "mattermost"
        assert len(p.get_nodes()) >= 10


class TestSupabasePlugin:
    """Test Supabase plugin."""

    def test_metadata(self):
        from common_lib.modules.plugins.native.supabase.supabase_plugin import SupabasePlugin
        p = SupabasePlugin()
        assert p.id == "supabase"
        assert len(p.get_nodes()) >= 10


class TestNextcloudPlugin:
    """Test Nextcloud plugin."""

    def test_metadata(self):
        from common_lib.modules.plugins.native.nextcloud.nextcloud_plugin import NextcloudPlugin
        p = NextcloudPlugin()
        assert p.id == "nextcloud"
        assert len(p.get_nodes()) >= 10


class TestMeilisearchPlugin:
    """Test Meilisearch plugin."""

    def test_metadata(self):
        from common_lib.modules.plugins.native.meilisearch.meilisearch_plugin import MeilisearchPlugin
        p = MeilisearchPlugin()
        assert p.id == "meilisearch"
        assert len(p.get_nodes()) >= 10


class TestDiscoursePlugin:
    """Test Discourse plugin."""

    def test_metadata(self):
        from common_lib.modules.plugins.native.discourse.discourse_plugin import DiscoursePlugin
        p = DiscoursePlugin()
        assert p.id == "discourse"
        assert len(p.get_nodes()) >= 10
