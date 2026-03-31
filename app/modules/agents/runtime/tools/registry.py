"""
agents/runtime/tools/registry.py
----------------------------------
Static metadata catalogue for the runtime agent's built-in tools.

Deliberately decoupled from handlers (no imports of callables) to avoid
circular references. Handlers are resolved at load-agent time via
``build_builtin_tools(ctx)``.

Convention is intentionally generic so future runtimes (skills, workflows,
prompts) can define their own registries following the same shape.
"""
from typing import Any, Dict, List, Optional


BUILTIN_TOOL_REGISTRY: List[Dict[str, Any]] = [
    {
        "id":          "get_current_weather",
        "name":        "Weather Lookup",
        "description": "Get the current weather conditions for a given location.",
        "category":    "demo",
    },
    {
        "id":          "calculate_math",
        "name":        "Math Calculator",
        "description": "Safely evaluate simple numeric expressions (e.g. '2 + 2 * 3').",
        "category":    "demo",
    },
    {
        "id":          "query_capability_inventory",
        "name":        "Capability Inventory",
        "description": "Search and list all tools, skills, and workflows available to this agent.",
        "category":    "system",
    },
    {
        "id":          "remember_info",
        "name":        "Remember Info",
        "description": "Store a key/value fact or preference in the agent's structured state.",
        "category":    "system",
    },
    {
        "id":          "extract_and_remember_hints",
        "name":        "Hint Extractor",
        "description": "Auto-extract names, preferences, and labels from the current conversation.",
        "category":    "system",
    },
]


def get_tool_meta(tool_id: str) -> Optional[Dict[str, Any]]:
    """Return metadata for a single tool ID, or None."""
    return next((t for t in BUILTIN_TOOL_REGISTRY if t["id"] == tool_id), None)


def get_tools_by_category() -> Dict[str, List[Dict]]:
    """Return a category → list-of-metadata dict."""
    groups: Dict[str, List[Dict]] = {}
    for t in BUILTIN_TOOL_REGISTRY:
        groups.setdefault(t["category"], []).append(t)
    return groups
