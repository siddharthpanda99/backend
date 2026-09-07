"""Install pipeline for the plugin server."""

from app.plugin_server.plugins_manager.installer import (
    install_plugin,
    uninstall_plugin,
    InstallResult,
    SourceType,
    write_starter_adapter,
    write_plugin_init,
)
from app.plugin_server.plugins_manager.hide import (
    is_hidden,
    hide_plugin,
    unhide_plugin,
    list_visible_plugins,
    list_hidden_plugins,
    HIDDEN_MARKER,
)

__all__ = [
    "install_plugin",
    "uninstall_plugin",
    "InstallResult",
    "SourceType",
    "write_starter_adapter",
    "write_plugin_init",
    "is_hidden",
    "hide_plugin",
    "unhide_plugin",
    "list_visible_plugins",
    "list_hidden_plugins",
    "HIDDEN_MARKER",
]
