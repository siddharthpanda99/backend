"""Collections — MCP tool for collection search.

Exposes the collection search API as an MCP tool so agents can use it
during conversations. When a collection is attached to a session,
the agent's knowledge boundary is that collection.

If no collection is attached, the whole platform is available.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger(__name__)


def register_collection_tools(mcp: FastMCP) -> None:
    """Register all Collection tools with the MCP server."""

    @mcp.tool()
    def collection_search(
        query: str,
        collection_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """Search within a collection or across all collections.

        When a collection_id is provided, searches only within that collection
        and its sub-collections (knowledge boundary).

        When a session_id is provided, finds the collection attached to that
        session and searches within it.

        If neither is provided, searches across ALL available collections.

        Args:
            query: Search query string
            collection_id: Optional collection ID to search within
            session_id: Optional session ID (finds attached collection)
            limit: Max results (default 20)

        Returns:
            Search results as formatted text
        """
        from common_lib.modules.data_storage.database.connection import get_session as get_db
        from common_lib.modules.knowledge_engine.knowledge_hub.collections.service import CollectionService

        try:
            with get_db() as session:
                # If session_id provided, find attached collection
                if session_id and not collection_id:
                    from common_lib.modules.knowledge_engine.knowledge_hub.collections.models import CollectionRecord
                    from sqlmodel import select
                    stmt = select(CollectionRecord).where(
                        CollectionRecord.attached_session_id == session_id
                    )
                    attached = session.exec(stmt).first()
                    if attached:
                        collection_id = attached.id

                if collection_id:
                    # Search within collection boundary
                    results = CollectionService.search_in_collection(
                        session, collection_id, query, limit=limit
                    )
                    if not results:
                        return f"No results found for '{query}' in collection."

                    lines = [f"Search results for '{query}' (collection scope):\n"]
                    for r in results:
                        lines.append(
                            f"- [{r['type']}] {r['title']}\n"
                            f"  {r.get('content_preview', '')[:200]}\n"
                        )
                    return "\n".join(lines)
                else:
                    # No collection boundary — search across ALL collections
                    all_collections = CollectionService.list_collections(session)
                    if not all_collections:
                        return f"No results found for '{query}' (no collections exist)."

                    all_results = []
                    for col in all_collections:
                        col_results = CollectionService.search_in_collection(
                            session, col.id, query, limit=limit
                        )
                        all_results.extend(col_results)

                    all_results.sort(key=lambda r: r.get("score", 0), reverse=True)
                    all_results = all_results[:limit]

                    if not all_results:
                        return f"No results found for '{query}'."

                    lines = [f"Search results for '{query}' (platform-wide, {len(all_collections)} collections):\n"]
                    for r in all_results:
                        lines.append(
                            f"- [{r['type']}] {r['title']}\n"
                            f"  {r.get('content_preview', '')[:200]}\n"
                        )
                    return "\n".join(lines)

        except Exception as e:
            logger.exception("Collection search failed")
            return f"Search error: {e}"

    @mcp.tool()
    def collection_list() -> str:
        """List all available collections.

        Returns the collection tree showing all collections, their items,
        and nesting structure. Use this to discover what collections
        exist before searching within one.

        Returns:
            Collection tree as formatted text
        """
        from common_lib.modules.data_storage.database.connection import get_session as get_db
        from common_lib.modules.knowledge_engine.knowledge_hub.collections.service import CollectionService

        try:
            with get_db() as session:
                tree = CollectionService.get_full_tree(session)
                collections = tree.get("collections", [])

                if not collections:
                    return "No collections found. Create one via the Collections API."

                lines = [f"Collections ({tree.get('total', 0)} root collections):\n"]

                def _render(nodes, indent=0):
                    for node in nodes:
                        prefix = "  " * indent
                        lines.append(
                            f"{prefix}- {node['name']} "
                            f"(id={node['id']}, items={node['item_count']}, "
                            f"descendants={node['total_descendant_count']})"
                        )
                        if node.get("description"):
                            lines.append(f"{prefix}  {node['description'][:100]}")
                        _render(node.get("children", []), indent + 1)

                _render(collections)
                return "\n".join(lines)

        except Exception as e:
            logger.exception("Collection list failed")
            return f"Error listing collections: {e}"

    @mcp.tool()
    def collection_get_sources(collection_id: str) -> str:
        """Get all data sources in a collection (flattened).

        Recursively resolves all items in a collection tree and returns
        a flat list of source references (files, APIs, projects, notes).

        Args:
            collection_id: The collection ID to inspect

        Returns:
            Flat list of sources as formatted text
        """
        from common_lib.modules.data_storage.database.connection import get_session as get_db
        from common_lib.modules.knowledge_engine.knowledge_hub.collections.service import CollectionService

        try:
            with get_db() as session:
                sources = CollectionService.get_all_source_ids(session, collection_id)

                if not sources:
                    return f"Collection {collection_id} has no sources."

                lines = [f"Sources in collection {collection_id} ({len(sources)} total):\n"]
                for src in sources:
                    lines.append(f"- [{src['item_type']}] {src['source_id']}")
                return "\n".join(lines)

        except Exception as e:
            logger.exception("Collection sources failed")
            return f"Error: {e}"
