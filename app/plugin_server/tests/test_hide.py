"""Tests for the hide/unhide plugin lifecycle."""

import pytest
from pathlib import Path


@pytest.fixture
def plugins_root(tmp_path):
    """Create a fake plugins root with one valid visible plugin."""
    (tmp_path / "plugin_a").mkdir()
    # Use a real BaseAdapter from SDK (not a stub class)
    (tmp_path / "plugin_a" / "__init__.py").write_text(
        "PLUGIN_ID = 'plugin_a'\n"
        "from common_lib.modules.plugin_sdk import BaseAdapter\n"
        "from common_lib.modules.plugins.base import BaseToolPlugin\n"
        "class _A(BaseAdapter):\n"
        "    def discover(self):\n"
        "        return []\n"
        "ADAPTER_CLASS = _A\n"
    )
    return tmp_path


class TestHideUnhide:
    def test_initial_state_all_visible(self, plugins_root):
        from app.plugin_server.plugins_manager.hide import (
            list_visible_plugins,
            list_hidden_plugins,
        )

        assert [p.name for p in list_visible_plugins(plugins_root)] == ["plugin_a"]
        assert list_hidden_plugins(plugins_root) == []

    def test_hide_moves_to_hidden_dir(self, plugins_root):
        from app.plugin_server.plugins_manager.hide import (
            hide_plugin,
            list_visible_plugins,
            list_hidden_plugins,
        )

        ok = hide_plugin(plugins_root / "plugin_a")
        assert ok is True
        assert (plugins_root / ".hidden" / "plugin_a").exists()
        # Marker file
        assert (plugins_root / ".hidden" / "plugin_a" / ".hidden").exists()
        # No longer visible
        assert [p.name for p in list_visible_plugins(plugins_root)] == [".hidden"]
        # Now hidden
        assert [p.name for p in list_hidden_plugins(plugins_root)] == ["plugin_a"]

    def test_hide_is_idempotent(self, plugins_root):
        from app.plugin_server.plugins_manager.hide import hide_plugin

        assert hide_plugin(plugins_root / "plugin_a") is True
        # Second call is a no-op (returns False because already hidden)
        assert hide_plugin(plugins_root / "plugin_a") is False

    def test_unhide_restores(self, plugins_root):
        from app.plugin_server.plugins_manager.hide import (
            hide_plugin,
            unhide_plugin,
            list_visible_plugins,
        )

        hide_plugin(plugins_root / "plugin_a")
        ok = unhide_plugin(plugins_root / ".hidden" / "plugin_a")
        assert ok is True
        assert (plugins_root / "plugin_a").exists()
        assert not (plugins_root / ".hidden" / "plugin_a").exists()
        assert "plugin_a" in [p.name for p in list_visible_plugins(plugins_root)]

    def test_unhide_blocked_if_visible_exists(self, plugins_root):
        from app.plugin_server.plugins_manager.hide import (
            hide_plugin,
            unhide_plugin,
        )

        hide_plugin(plugins_root / "plugin_a")
        # Re-create plugin_a at the top level
        (plugins_root / "plugin_a").mkdir()
        # Now unhide should fail (collision)
        assert unhide_plugin(plugins_root / ".hidden" / "plugin_a") is False

    def test_hide_nonexistent_returns_false(self, plugins_root):
        from app.plugin_server.plugins_manager.hide import hide_plugin

        assert hide_plugin(plugins_root / "nope") is False

    def test_discovery_skips_hidden(self, plugins_root):
        from app.plugin_server.plugins_manager.hide import hide_plugin

        # We don't test full discovery here (the discovery walker
        # has its own tests in test_routes.py). We just verify that
        # the hide function correctly moves the plugin to .hidden/
        # and that is_hidden returns True afterwards.
        assert hide_plugin(plugins_root / "plugin_a") is True
        from app.plugin_server.plugins_manager.hide import (
            is_hidden,
            list_visible_plugins,
        )

        assert is_hidden(plugins_root / "plugin_a") is False  # moved
        assert is_hidden(plugins_root / ".hidden" / "plugin_a") is True
        assert "plugin_a" not in [p.name for p in list_visible_plugins(plugins_root)]

    def test_marker_file_alone_hides(self, plugins_root):
        """A plugin folder with just a .hidden marker is also hidden."""
        from app.plugin_server.plugins_manager.hide import (
            is_hidden,
            list_visible_plugins,
        )

        # Drop a .hidden marker in plugin_a without moving it
        (plugins_root / "plugin_a" / ".hidden").write_text("manual")
        assert is_hidden(plugins_root / "plugin_a") is True
        assert "plugin_a" not in [p.name for p in list_visible_plugins(plugins_root)]
