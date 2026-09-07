"""Plugin manifest for data_analytics_toolkit."""

from __future__ import annotations

PLUGIN_ID = "data_analytics_toolkit"

try:
    from .adapater import DataAnalyticsAdapter

    ADAPTER_CLASS = DataAnalyticsAdapter
except ImportError as e:
    ADAPTER_CLASS = None
    import logging

    logging.getLogger(__name__).warning(
        f"Plugin {PLUGIN_ID}: failed to import adapter: {e}"
    )
