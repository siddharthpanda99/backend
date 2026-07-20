"""MCP tools for semantic multi-layer tool search.

Lets AI agents find the right tool from 2,900+ candidates using:
  - Category/audience/tag pre-filters (fast narrowing)
  - Keyword substring match
  - Semantic similarity (sentence-transformers embeddings)

Usage (MCP agent):
  tool_search(query="transcribe audio file spanish")
  tool_search(query="create user with permissions", category="auth", audience="executor")
  tool_search_categories()
  tool_search_tags()
"""

import logging
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from app.mcp import search_engine

logger = logging.getLogger("mcp.tools.tool_search")


def register_tool_search_tools(mcp: FastMCP):
    """Register tool search & discovery tools on the MCP server."""

    async def _ensure_index():
        """Build the search index from the live MCP tool list."""
        tools_raw = await mcp.list_tools()
        tool_dicts = [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.inputSchema,
            }
            for t in tools_raw
        ]
        return search_engine.build_index(tool_dicts)

    @mcp.tool()
    async def tool_search(
        query: str = "",
        category: Optional[str] = None,
        audience: Optional[str] = None,
        tags: Optional[List[str]] = None,
        keyword: Optional[str] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """Multi-layer semantic search across all MCP tools.

        Use this to find the most relevant tool for a user's natural-language
        request.  Supports pre-filters (category, audience, tags, keyword) to
        narrow the candidate pool before the expensive semantic match.

        Args:
            query:        Natural-language description of what the user wants
                          (e.g. "transcribe an audio file to text in Spanish").
            category:     Exact category/module name (e.g. "audio", "auth",
                          "memory").  Get full list via tool_search_categories().
            audience:     Who will call the tool — "planner", "executor",
                          "system".
            tags:         Any-of tag keywords (e.g. ["search", "rag"]).
                          Get full list via tool_search_tags().
            keyword:      Fast substring filter on tool name + description
                          (bypasses semantic model).
            top_k:        Maximum number of results (default 20, max 100).

        Returns:
            List of matched tools with name, description, inputSchema, and
            a 'score' (cosine similarity, 0-1) + 'match_type' field.
        """
        await _ensure_index()
        top_k = min(top_k, 100)

        # Ensure embeddings are computed in a thread so we don't block the event loop
        index = search_engine.ensure_index()
        await search_engine.compute_embeddings_async(index)

        return search_engine.search_tools(
            query=query,
            category=category,
            audience=audience,
            tags=tags,
            keyword=keyword,
            top_k=top_k,
        )

    @mcp.tool()
    async def tool_search_categories() -> List[Dict[str, Any]]:
        """List all tool categories with their tool counts.

        Use this to discover which domains are available before narrowing
        a search (e.g. "audio", "memory", "auth", "knowledge").
        """
        await _ensure_index()
        return search_engine.list_categories()

    @mcp.tool()
    async def tool_search_tags(top_n: int = 30) -> List[Dict[str, Any]]:
        """List the most common tags across all tools with counts.

        Tags are keywords like "search", "rag", "database", "embedding".
        Use this to discover filtering keywords for tool_search().
        """
        await _ensure_index()
        return search_engine.list_tags(top_n=min(top_n, 100))

    @mcp.tool()
    async def tool_search_audiences() -> List[Dict[str, Any]]:
        """List all tool audiences with counts.

        Audiences: "planner" (task planning), "executor" (direct execution),
        "system" (admin/ops).  Use to narrow tool_search() by audience.
        """
        await _ensure_index()
        return search_engine.list_audiences()

    @mcp.tool()
    async def tool_get_details(tool_name: str) -> Dict[str, Any]:
        """Get the full metadata (including inputSchema) for one tool by name.

        Args:
            tool_name: Exact name of the tool (e.g. "transcribe_audio").
        """
        await _ensure_index()
        t = search_engine.get_tool(tool_name)
        if t is None:
            return {"error": f"Tool '{tool_name}' not found"}
        return t

    @mcp.tool()
    async def tool_search_suggest(prefix: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Quick name-based suggestion for autocomplete-like use cases.

        Args:
            prefix: Start of a tool name (e.g. "trans" → transcode,
                    transcribe, translate).
            top_k:  Max suggestions (default 10).
        """
        await _ensure_index()
        p = prefix.lower()
        index = search_engine.ensure_index()
        matches = []
        for t in index["tools"]:
            name = t.get("name", "")
            if name.lower().startswith(p):
                matches.append(
                    {"name": name, "description": (t.get("description") or "")[:120]}
                )
            if len(matches) >= top_k:
                break
        return matches

    @mcp.tool()
    async def tool_search_rebuild() -> Dict[str, Any]:
        """Force-rebuild the search index (clears embedding cache).

        Call this after new tools are registered at runtime to ensure the
        search index reflects the latest tool set.
        """
        await _ensure_index()
        search_engine.rebuild_index()
        # Rebuild with latest tool list
        await _ensure_index()
        index = search_engine.ensure_index()
        return {
            "status": "ok",
            "total_tools": len(index["tools"]),
        }

    logger.info("Tool Search: 7 MCP tools registered")
