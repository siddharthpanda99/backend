"""Panel Discovery — auto-discover BasePanel subclasses.

Each plugin's `panel/` subfolder may contain a `__init__.py`
that exposes a `PANEL_CLASS` (analogous to how the plugin's
`__init__.py` exposes `ADAPTER_CLASS`).

This scanner walks every installed plugin folder, looks for
`panel/__init__.py`, and instantiates any declared
`PANEL_CLASS`. Each panel is then wired to its plugin's
BaseToolPlugin instance.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from app.plugin_server.panels import BasePanel
from app.plugin_server.panels.registry import PanelRegistry

logger = logging.getLogger(__name__)


def discover_panels(
    plugins_root: Path,
    plugin_id_to_instance: dict[str, Any],
) -> list[BasePanel]:
    """Walk `plugins_root` and instantiate any panel found.

    Args:
        plugins_root: The directory containing installed plugin
            folders (e.g. ``Backend Monorepo/.../app/plugin_server/plugins``).
        plugin_id_to_instance: Mapping of plugin id -> loaded
            BaseToolPlugin instance. Each panel is wired to its
            plugin via ``panel.plugin = instance``.

    Returns:
        List of BasePanel instances, ready to register.
    """
    panels: list[BasePanel] = []
    if not plugins_root.exists():
        return panels

    for plugin_dir in sorted(plugins_root.iterdir()):
        if not plugin_dir.is_dir():
            continue
        if plugin_dir.name.startswith("_") or plugin_dir.name.startswith("."):
            continue
        # Skip hidden (soft-deleted) plugins
        from app.plugin_server.plugins_manager.hide import is_hidden

        if is_hidden(plugin_dir):
            continue
        panel_init = plugin_dir / "panel" / "__init__.py"
        if not panel_init.exists():
            continue

        # Add the plugin's parent to sys.path so the panel's
        # import of the sibling adapter works.
        parent = str(plugins_root.resolve())
        if parent not in sys.path:
            sys.path.insert(0, parent)

        module_name = f"{plugin_dir.name}.panel"
        if module_name in sys.modules:
            del sys.modules[module_name]

        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.warning(f"Panel discovery: failed to import {module_name}: {e}")
            continue

        panel_class = getattr(module, "PANEL_CLASS", None)
        if panel_class is None:
            continue
        if not isinstance(panel_class, type) or not issubclass(panel_class, BasePanel):
            continue

        # Skip if hidden=True
        if getattr(panel_class, "hidden", False):
            continue

        # Instantiate and wire to its plugin
        try:
            panel = panel_class()
        except Exception as e:
            logger.warning(f"Panel discovery: {panel_class.__name__}() failed: {e}")
            continue

        # Bind to the plugin instance
        plugin_instance = plugin_id_to_instance.get(panel.id)
        if plugin_instance is None:
            logger.debug(
                f"Panel {panel.id}: no plugin instance available; "
                f"panel will run with unbound plugin"
            )
        else:
            panel.plugin = plugin_instance

        panels.append(panel)
        logger.info(
            f"Panel discovery: {plugin_dir.name}.panel "
            f"-> {panel_class.__name__} (bound={plugin_instance is not None})"
        )

    return panels


def register_all_panels(
    plugins_root: Path,
    plugin_id_to_instance: dict[str, Any],
    registry: PanelRegistry | None = None,
) -> int:
    """Discover all panels and register them. Returns count registered."""
    if registry is None:
        from app.plugin_server.panels.registry import get_panel_registry

        registry = get_panel_registry()

    panels = discover_panels(plugins_root, plugin_id_to_instance)
    for panel in panels:
        try:
            panel.warm_up()
        except Exception as e:
            logger.warning(f"Panel {panel.id} warm_up failed: {e}")
        registry.register(panel)
    return len(panels)


__all__ = ["discover_panels", "register_all_panels"]
