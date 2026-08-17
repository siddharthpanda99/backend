"""Module 25 — Search, Catalog & Data Discovery MCP tools.

Agent-facing tools for search, catalog, glossary, tags, relationships,
recommendations, and dashboard.
"""
from typing import Any, Dict, List, Optional
from app.mcp.fastmcp_compat import FastMCP

from common_lib.modules.db_studio.discovery.service import DiscoveryService

svc = DiscoveryService()


def register_discovery_tools(mcp: FastMCP):
    """Register all discovery tools with the MCP server."""

    @mcp.tool()
    async def discovery_search(query: str, asset_types: Optional[List[str]] = None,
                                tags: Optional[List[str]] = None, limit: int = 20,
                                offset: int = 0) -> Dict[str, Any]:
        """Full-text search across all indexed assets with faceted filters"""
        from common_lib.modules.db_studio.discovery.schemas import SearchRequest
        req = SearchRequest(query=query, asset_types=asset_types, tags=tags,
                            limit=limit, offset=offset)
        result = svc.search(req)
        return result.model_dump()

    @mcp.tool()
    async def discovery_search_suggestions(prefix: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get search suggestions for autocomplete"""
        suggestions = svc.get_suggestions(prefix, limit)
        return [s.model_dump() for s in suggestions]

    @mcp.tool()
    async def discovery_recent_searches(user_id: str = "anonymous", limit: int = 20) -> List[Any]:
        """Get recent search queries"""
        return svc.get_recent_searches(user_id, limit)

    @mcp.tool()
    async def discovery_index_asset(asset_type: str, asset_id: str, title: str,
                                     description: Optional[str] = None,
                                     content: Optional[str] = None,
                                     tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Index or update an asset in the search index"""
        from common_lib.modules.db_studio.discovery.schemas import IndexRequest
        req = IndexRequest(asset_type=asset_type, asset_id=asset_id, title=title,
                           description=description, content=content, tags=tags)
        result = svc.index_asset(req)
        return result.model_dump()

    @mcp.tool()
    async def discovery_create_catalog_asset(name: str, asset_type: str,
                                              description: Optional[str] = None,
                                              classification: Optional[str] = None) -> Dict[str, Any]:
        """Create a new catalog asset entry"""
        from common_lib.modules.db_studio.discovery.schemas import CatalogAssetCreate
        req = CatalogAssetCreate(name=name, asset_type=asset_type, description=description,
                                 classification=classification)
        result = svc.create_catalog_asset(req)
        return result.model_dump()

    @mcp.tool()
    async def discovery_get_catalog_asset(asset_id: str) -> Optional[Dict[str, Any]]:
        """Get a catalog asset by ID"""
        result = svc.get_catalog_asset(asset_id)
        return result.model_dump() if result else None

    @mcp.tool()
    async def discovery_list_catalog(
        asset_type: Optional[str] = None,
        classification: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List catalog assets with optional filters"""
        items, total = svc.list_catalog_assets(
            asset_type=asset_type, classification=classification,
            limit=limit, offset=offset,
        )
        return {"total": total, "items": [i.model_dump() for i in items]}

    @mcp.tool()
    async def discovery_delete_catalog_asset(asset_id: str) -> Dict[str, bool]:
        """Delete a catalog asset by ID"""
        ok = svc.delete_catalog_asset(asset_id)
        return {"ok": ok}

    @mcp.tool()
    async def discovery_create_glossary_term(term: str, definition: str,
                                              domain: Optional[str] = None) -> Dict[str, Any]:
        """Create a new business glossary term"""
        from common_lib.modules.db_studio.discovery.schemas import GlossaryTermCreate
        req = GlossaryTermCreate(term=term, definition=definition, domain=domain)
        result = svc.create_glossary_term(req)
        return result.model_dump()

    @mcp.tool()
    async def discovery_list_glossary(
        domain: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        """List glossary terms with optional filters"""
        items, total = svc.list_glossary_terms(domain=domain, limit=limit, offset=offset)
        return {"total": total, "items": [i.model_dump() for i in items]}

    @mcp.tool()
    async def discovery_add_tag(tag_name: str, asset_type: str, asset_id: str) -> Dict[str, Any]:
        """Add a tag to an asset"""
        from common_lib.modules.db_studio.discovery.schemas import TagCreate
        req = TagCreate(tag_name=tag_name, asset_type=asset_type, asset_id=asset_id)
        result = svc.add_tag(req)
        return result.model_dump()

    @mcp.tool()
    async def discovery_get_tags(asset_type: str, asset_id: str) -> List[Dict[str, Any]]:
        """Get all tags for an asset"""
        tags = svc.get_tags_for_asset(asset_type, asset_id)
        return [t.model_dump() for t in tags]

    @mcp.tool()
    async def discovery_popular_tags(limit: int = 20) -> List[Dict[str, Any]]:
        """Get the most popular tags across all assets"""
        tags = svc.get_popular_tags(limit)
        return [t.model_dump() for t in tags]

    @mcp.tool()
    async def discovery_create_relationship(source_asset_type: str, source_asset_id: str,
                                             target_asset_type: str, target_asset_id: str,
                                             relationship_type: str) -> Dict[str, Any]:
        """Create a relationship between two assets"""
        from common_lib.modules.db_studio.discovery.schemas import RelationshipCreate
        req = RelationshipCreate(source_asset_type=source_asset_type, source_asset_id=source_asset_id,
                                 target_asset_type=target_asset_type, target_asset_id=target_asset_id,
                                 relationship_type=relationship_type)
        result = svc.create_relationship(req)
        return result.model_dump()

    @mcp.tool()
    async def discovery_get_relationships(asset_type: str, asset_id: str) -> List[Dict[str, Any]]:
        """Get all relationships for an asset"""
        rels = svc.get_relationships(asset_type, asset_id)
        return [r.model_dump() for r in rels]

    @mcp.tool()
    async def discovery_generate_recommendations(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Generate personalized recommendations for a user"""
        recs = svc.generate_recommendations(user_id, limit)
        return [r.model_dump() for r in recs]

    @mcp.tool()
    async def discovery_list_recommendations(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """List recommendations for a user"""
        recs = svc.list_recommendations(user_id, limit)
        return [r.model_dump() for r in recs]

    @mcp.tool()
    async def discovery_dashboard() -> Dict[str, Any]:
        """Get discovery dashboard with aggregated stats"""
        dash = svc.get_dashboard()
        return dash.model_dump()
