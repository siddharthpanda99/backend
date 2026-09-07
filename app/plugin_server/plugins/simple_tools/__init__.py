"""Plugin manifest for simple_tools."""

from __future__ import annotations

PLUGIN_ID = "simple_tools"

try:
    from .adapater import SimpleToolsAdapter

    ADAPTER_CLASS = SimpleToolsAdapter
except ImportError as e:
    ADAPTER_CLASS = None
    import logging

    logging.getLogger(__name__).warning(
        f"Plugin {PLUGIN_ID}: failed to import adapter: {e}"
    )
