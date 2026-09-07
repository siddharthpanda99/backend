"""Plugin Server — Auto-discovery walker.

Scans the ``plugins/`` directory for installed plugin folders,
imports each one's ``__init__.py``, and instantiates the
``ADAPTER_CLASS`` it declares. The adapter's :meth:`discover`
method yields BaseToolPlugin instances which are then registered
with the engine.

The walker is robust to:

- Missing __init__.py → skip with warning
- Import errors → skip with error, log to error log
- Missing ADAPTER_CLASS → skip with warning
- ADAPTER_CLASS = None (auto-gen stub not yet replaced) → skip
- Multiple plugins per adapter (yields list) → all registered
- Disposed adapter state (warm_up throws) → mark plugin FAILED
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredPlugin:
    """One BaseToolPlugin instance produced by an adapter."""

    plugin_id: str
    plugin_instance: Any
    plugin_dir: Path
    adapter_class_name: str
    warm_up_ok: bool = True
    warm_up_error: str = ""


@dataclass
class DiscoveryResult:
    """Aggregate result of a discovery scan."""

    plugins: list[DiscoveredPlugin] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "plugins": [
                {
                    "plugin_id": p.plugin_id,
                    "plugin_dir": str(p.plugin_dir),
                    "adapter_class": p.adapter_class_name,
                    "warm_up_ok": p.warm_up_ok,
                }
                for p in self.plugins
            ],
            "skipped": self.skipped,
            "errors": self.errors,
        }


class PluginDiscovery:
    """Walks the plugins/ directory and loads installed plugins.

    Usage::

        discovery = PluginDiscovery(plugins_root=Path("plugins"))
        result = discovery.scan()
        for p in result.plugins:
            register_with_engine(p.plugin_instance)
    """

    def __init__(self, plugins_root: str | Path):
        self.plugins_root = Path(plugins_root)
        self._lock = threading.RLock()

    def scan(self) -> DiscoveryResult:
        """Scan the plugins_root and return a DiscoveryResult."""
        with self._lock:
            result = DiscoveryResult()
            if not self.plugins_root.exists():
                logger.info(
                    f"PluginDiscovery: {self.plugins_root} does not exist; "
                    f"returning empty result"
                )
                return result

            # Skip hidden (soft-deleted) plugin folders
            from app.plugin_server.plugins_manager.hide import is_hidden

            for entry in sorted(self.plugins_root.iterdir()):
                if not entry.is_dir():
                    continue
                if entry.name.startswith("_") or entry.name.startswith("."):
                    continue
                if is_hidden(entry):
                    result.skipped.append(
                        {
                            "plugin_id": entry.name,
                            "plugin_dir": str(entry),
                            "reason": "plugin is hidden (soft-deleted)",
                        }
                    )
                    continue
                self._load_one(entry, result)

            logger.info(
                f"PluginDiscovery: {len(result.plugins)} plugins loaded, "
                f"{len(result.skipped)} skipped, {len(result.errors)} errors"
            )
            return result

    def _load_one(self, plugin_dir: Path, result: DiscoveryResult) -> None:
        """Try to load one plugin folder. Updates result in-place."""
        init_path = plugin_dir / "__init__.py"
        if not init_path.exists():
            result.skipped.append(
                {
                    "plugin_id": plugin_dir.name,
                    "plugin_dir": str(plugin_dir),
                    "reason": "no __init__.py",
                }
            )
            return

        # Add the plugin's parent to sys.path so the package import
        # works (plugins_root is the parent of each plugin folder).
        parent = str(self.plugins_root.resolve())
        if parent not in sys.path:
            sys.path.insert(0, parent)

        module_name = plugin_dir.name
        try:
            # Re-import in case the module was loaded before
            if module_name in sys.modules:
                del sys.modules[module_name]
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.exception(f"PluginDiscovery: failed to import {module_name}: {e}")
            result.errors.append(
                {
                    "plugin_id": plugin_dir.name,
                    "plugin_dir": str(plugin_dir),
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            return

        # The __init__ module must declare ADAPTER_CLASS
        adapter_class = getattr(module, "ADAPTER_CLASS", None)
        declared_id = getattr(module, "PLUGIN_ID", None)
        if adapter_class is None:
            result.skipped.append(
                {
                    "plugin_id": plugin_dir.name,
                    "plugin_dir": str(plugin_dir),
                    "reason": "ADAPTER_CLASS is None (stub not yet implemented?)",
                }
            )
            return

        if declared_id is not None and declared_id != plugin_dir.name:
            result.errors.append(
                {
                    "plugin_id": plugin_dir.name,
                    "plugin_dir": str(plugin_dir),
                    "error": (
                        f"PLUGIN_ID={declared_id!r} does not match folder name "
                        f"{plugin_dir.name!r}"
                    ),
                }
            )
            return

        # Instantiate the adapter
        try:
            adapter = adapter_class(
                plugin_id=plugin_dir.name,
                plugin_dir=plugin_dir,
            )
        except Exception as e:
            result.errors.append(
                {
                    "plugin_id": plugin_dir.name,
                    "plugin_dir": str(plugin_dir),
                    "error": f"adapter init failed: {e}",
                }
            )
            return

        # Call discover() to get the BaseToolPlugin instances
        try:
            discovered = adapter.discover()
        except Exception as e:
            logger.exception(
                f"PluginDiscovery: {plugin_dir.name}.discover() raised: {e}"
            )
            result.errors.append(
                {
                    "plugin_id": plugin_dir.name,
                    "plugin_dir": str(plugin_dir),
                    "error": f"discover() raised: {e}",
                }
            )
            return

        # Normalize: discover() can return one or many
        if not isinstance(discovered, (list, tuple)):
            discovered = [discovered]

        for instance in discovered:
            plugin_id = getattr(instance, "id", plugin_dir.name)
            warm_up_ok = True
            warm_up_error = ""

            # Try warm-up
            try:
                adapter.warm_up()
            except Exception as e:
                warm_up_ok = False
                warm_up_error = str(e)
                logger.warning(
                    f"PluginDiscovery: {plugin_dir.name} warm_up failed: {e}"
                )

            result.plugins.append(
                DiscoveredPlugin(
                    plugin_id=plugin_id,
                    plugin_instance=instance,
                    plugin_dir=plugin_dir,
                    adapter_class_name=adapter_class.__name__,
                    warm_up_ok=warm_up_ok,
                    warm_up_error=warm_up_error,
                )
            )

    def load_one(self, plugin_id: str) -> DiscoveredPlugin | None:
        """Load just one plugin by id. Returns None if not found."""
        plugin_dir = self.plugins_root / plugin_id
        if not plugin_dir.exists():
            return None
        result = DiscoveryResult()
        self._load_one(plugin_dir, result)
        return result.plugins[0] if result.plugins else None


__all__ = [
    "PluginDiscovery",
    "DiscoveryResult",
    "DiscoveredPlugin",
]
