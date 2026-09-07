"""Plugin manifest for hf_recommender — auto-generated.

This file is imported by the plugin server's auto-discovery
walker. The walker looks for:
  - PLUGIN_ID  : must match the folder name
  - ADAPTER_CLASS : the adapter class to instantiate
"""

from __future__ import annotations

# Must match the folder name. The discovery walker verifies this.
PLUGIN_ID = "hf_recommender"

try:
    from .adapater import HfRecommenderAdapter

    ADAPTER_CLASS = HfRecommenderAdapter
except ImportError as e:
    ADAPTER_CLASS = None
    import logging

    logging.getLogger(__name__).warning(
        f"Plugin {PLUGIN_ID}: failed to import adapter: {e}"
    )
