"""Standalone MCP Server — ALL @node wrappers as individual MCP tools.

Serves 2,300+ @node-decorated functions across 88 modules as individual
MCP tools so that opencode (and any MCP client) can discover, inspect,
and INVOKE any backend capability directly.

Transport: stdio (spawned by opencode via mcp config in opencode.jsonc).

Usage:
    uv run python app/mcp/standalone_node_server.py
    uv run node-server                          # via pyproject.toml script
"""

import logging

from app.mcp.fastmcp_compat import FastMCP

from app.mcp.node_bridge import register_dynamic_node_tools

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("node-server")

mcp = FastMCP(
    "Node Registry",
    dependencies=["common_lib"],
)

# -- Meta-tools (keep for discovery/categorization) --------------------------

_NODES: list[dict] = []
_NODES_BY_NAME: dict[str, dict] = {}
_NODES_BY_CATEGORY: dict[str, list[dict]] = {}


def _ensure_nodes() -> None:
    global _NODES, _NODES_BY_NAME, _NODES_BY_CATEGORY
    if _NODES:
        return
    try:
        from common_lib.modules.plugins.nodes_registry import discover_nodes

        _NODES[:] = [n.to_dict() for n in discover_nodes()]
    except Exception as exc:
        logger.warning("discover_nodes() failed: %s", exc)
        _NODES[:] = []
    _NODES_BY_NAME.clear()
    _NODES_BY_CATEGORY.clear()
    for n in _NODES:
        name = n.get("name", "")
        if name:
            _NODES_BY_NAME[name] = n
        cat = n.get("category", "uncategorized")
        _NODES_BY_CATEGORY.setdefault(cat, []).append(n)


@mcp.tool()
def nodes_list_all(category: str | None = None) -> list[dict]:
    """List every @node wrapper. Optionally filter by exact category name."""
    _ensure_nodes()
    if category:
        return _NODES_BY_CATEGORY.get(category, [])
    return _NODES


@mcp.tool()
def nodes_list_categories() -> list[dict]:
    """List all node categories with their wrapper counts."""
    _ensure_nodes()
    counts: dict[str, int] = {}
    for n in _NODES:
        c = n.get("category", "unknown")
        counts[c] = counts.get(c, 0) + 1
    return [
        {"category": k, "count": v}
        for k, v in sorted(counts.items(), key=lambda x: -x[1])
    ]


@mcp.tool()
def nodes_search(query: str = "") -> list[dict]:
    """Full-text search across node names, descriptions, and tags."""
    _ensure_nodes()
    if not query:
        return _NODES
    q = query.lower()
    results = []
    for n in _NODES:
        if q in n.get("name", "").lower():
            results.append(n)
            continue
        if q in n.get("description", "").lower():
            results.append(n)
            continue
        if any(q in t.lower() for t in n.get("tags", [])):
            results.append(n)
            continue
    return results


@mcp.tool()
def nodes_get_details(node_name: str) -> dict:
    """Get the full metadata (including input/output schema) for one node."""
    _ensure_nodes()
    n = _NODES_BY_NAME.get(node_name)
    if n is None:
        return {"error": f"Node '{node_name}' not found"}
    return n


@mcp.tool()
def nodes_stats() -> dict:
    """Return aggregate statistics about the node registry."""
    _ensure_nodes()
    if not _NODES:
        return {"total": 0, "categories": 0, "top_tags": []}
    cats = set(n.get("category", "unknown") for n in _NODES)
    tag_counts: dict[str, int] = {}
    for n in _NODES:
        for t in n.get("tags", []):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    top = sorted(tag_counts.items(), key=lambda x: -x[1])[:10]
    return {
        "total": len(_NODES),
        "categories": len(cats),
        "top_tags": [{"tag": k, "count": v} for k, v in top],
    }


# -- Resources ---------------------------------------------------------------


@mcp.resource("node://summary")
def resource_summary() -> str:
    """Aggregate stats about the @node registry (markdown)."""
    _ensure_nodes()
    cats = nodes_list_categories()
    stats = nodes_stats()
    lines = [
        f"# @node Registry Summary",
        f"**Total wrappers:** {stats['total']}",
        f"**Categories:** {stats['categories']}",
        "",
        "## Categories",
    ]
    for c in cats:
        lines.append(f"- **{c['category']}**: {c['count']}")
    if stats["top_tags"]:
        lines.extend(["", "## Top Tags"])
        for t in stats["top_tags"]:
            lines.append(f"- {t['tag']}: {t['count']}")
    return "\n".join(lines)


@mcp.resource("node://category/{category}")
def resource_category(category: str) -> str:
    """All nodes in a given category (markdown)."""
    _ensure_nodes()
    nodes = _NODES_BY_CATEGORY.get(category, [])
    lines = [f"# Category: {category}  ({len(nodes)} nodes)", ""]
    for n in sorted(nodes, key=lambda x: x["name"]):
        desc = n.get("description", "")
        tags = ", ".join(n.get("tags", []))
        lines.append(f"## {n['name']}")
        if desc:
            lines.append(desc)
        if tags:
            lines.append(f"Tags: {tags}")
        lines.append("")
    return "\n".join(lines)


# -- Dynamic @node → MCP tool registration -----------------------------------


def main() -> None:
    # Register all 2,300+ @node wrappers as individual MCP tools
    count = register_dynamic_node_tools(mcp)
    logger.info(
        "Standalone Node Registry: %s @node wrappers registered as MCP tools", count
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
