"""Panel Registry — discovers and indexes all BasePanel subclasses.

A panel is registered in one of two ways:

  1. **Programmatic**: call ``PanelRegistry.register(panel_instance)``
     from anywhere (e.g. during the Plugin Server lifespan).

  2. **Auto-discovery** (planned): scan a `panels/` directory next
     to the plugin folder and import any ``panel.py``. Not yet
     implemented because all 3 example panels are bundled with
     the platform and registered explicitly in main.py.

The registry is a process-wide singleton; the REST API
(``GET /panels``, ``GET /panels/{id}``, ``POST /panels/{id}/render``)
queries it.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.plugin_server.panels import BasePanel

logger = logging.getLogger(__name__)


class PanelRegistry:
    """Process-wide registry of plugin panels."""

    def __init__(self) -> None:
        self._panels: dict[str, BasePanel] = {}
        self._lock = threading.RLock()

    def register(self, panel: BasePanel) -> BasePanel:
        """Register a panel instance. Returns the same instance."""
        if not isinstance(panel, BasePanel):
            raise TypeError(f"Expected BasePanel, got {type(panel).__name__}")
        if not panel.id:
            raise ValueError("Panel must have a non-empty id")
        with self._lock:
            existing = self._panels.get(panel.id)
            if existing is not None and existing is not panel:
                logger.warning(f"Panel {panel.id!r} already registered; replacing")
            self._panels[panel.id] = panel
        logger.info(f"PanelRegistry: registered {panel.id}")
        return panel

    def unregister(self, panel_id: str) -> bool:
        with self._lock:
            return self._panels.pop(panel_id, None) is not None

    def get(self, panel_id: str) -> BasePanel | None:
        with self._lock:
            return self._panels.get(panel_id)

    def list(self) -> list[BasePanel]:
        with self._lock:
            return list(self._panels.values())

    def list_specs(self) -> list[dict[str, Any]]:
        """Return a list of panel specs (for the UI launcher)."""
        with self._lock:
            return [panel.render("spec") for panel in self._panels.values()]


# ── Module-level singleton ────────────────────────────────────

_registry: PanelRegistry | None = None
_registry_lock = threading.Lock()


def get_panel_registry() -> PanelRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = PanelRegistry()
    return _registry


def reset_panel_registry() -> None:
    global _registry
    _registry = None


__all__ = ["PanelRegistry", "get_panel_registry", "reset_panel_registry"]
