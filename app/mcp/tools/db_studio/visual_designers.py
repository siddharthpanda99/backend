"""MCP tools for Visual Database Designers (UDS Module 05).

Exposes diagram management, reverse engineering, DDL generation,
schema comparison, and synchronization to agents.
"""

import logging

logger = logging.getLogger(__name__)


def register_visual_designers_tools(mcp_server):
    """Register all visual designer MCP tools."""

    from common_lib.modules.db_studio.visual_designers import (
        VisualDesignerService,
        DiagramCreate,
        DiagramUpdate,
        NodeCreate,
        NodeUpdate,
        EdgeCreate,
        EdgeUpdate,
        BulkNodesRequest,
        BulkEdgesRequest,
        LayoutCreate,
        ReverseEngineerRequest,
        DDLGenerateRequest,
        CompareRequest,
        SyncRequest,
        DesignTemplateCreate,
    )

    svc = VisualDesignerService()

    # ── Diagram CRUD ─────────────────────────────────────────────────

    @mcp_server.tool()
    async def designer_create_diagram(name: str, description: str = None,
                                       connection_id: str = None, schema_name: str = None,
                                       notation: str = "crowsfoot"):
        """Create a new visual database design diagram."""
        req = DiagramCreate(name=name, description=description,
                            connection_id=connection_id, schema_name=schema_name,
                            notation=notation)
        result = svc.create_diagram(req)
        return result.model_dump()

    @mcp_server.tool()
    async def designer_list_diagrams(search: str = None, connection_id: str = None,
                                      offset: int = 0, limit: int = 50):
        """List saved diagrams in the visual designer."""
        result = svc.list_diagrams(search, connection_id, offset=offset, limit=limit)
        return result.model_dump()

    @mcp_server.tool()
    async def designer_get_diagram(diagram_id: str):
        """Get a diagram by ID with full metadata."""
        result = svc.get_diagram(diagram_id)
        return result.model_dump() if result else {"error": "Diagram not found"}

    @mcp_server.tool()
    async def designer_update_diagram(diagram_id: str, name: str = None,
                                       description: str = None, theme: str = None):
        """Update diagram metadata."""
        req = DiagramUpdate(name=name, description=description, theme=theme)
        result = svc.update_diagram(diagram_id, req)
        return result.model_dump() if result else {"error": "Diagram not found"}

    @mcp_server.tool()
    async def designer_delete_diagram(diagram_id: str):
        """Delete a diagram and all its nodes, edges, and layouts."""
        success = svc.delete_diagram(diagram_id)
        return {"success": success}

    # ── Node Management ──────────────────────────────────────────────

    @mcp_server.tool()
    async def designer_add_node(diagram_id: str, entity_name: str,
                                 node_type: str = "table", entity_schema: str = "public",
                                 x: float = 100.0, y: float = 100.0):
        """Add a table/view node to a diagram."""
        req = NodeCreate(diagram_id=diagram_id, entity_name=entity_name,
                         node_type=node_type, entity_schema=entity_schema, x=x, y=y)
        result = svc.add_node(req)
        return result.model_dump()

    @mcp_server.tool()
    async def designer_list_nodes(diagram_id: str):
        """List all nodes in a diagram."""
        results = svc.list_nodes(diagram_id)
        return [r.model_dump() for r in results]

    @mcp_server.tool()
    async def designer_update_node(node_id: str, x: float = None, y: float = None,
                                    entity_name: str = None, notes: str = None):
        """Update a node's position or properties."""
        req = NodeUpdate(x=x, y=y, entity_name=entity_name, notes=notes)
        result = svc.update_node(node_id, req)
        return result.model_dump() if result else {"error": "Node not found"}

    @mcp_server.tool()
    async def designer_delete_node(node_id: str):
        """Delete a node and its connected edges."""
        success = svc.delete_node(node_id)
        return {"success": success}

    # ── Edge Management ──────────────────────────────────────────────

    @mcp_server.tool()
    async def designer_add_edge(diagram_id: str, source_node_id: str,
                                 target_node_id: str,
                                 relationship_type: str = "one_to_many",
                                 constraint_name: str = None):
        """Add a relationship edge between two nodes."""
        req = EdgeCreate(diagram_id=diagram_id, source_node_id=source_node_id,
                         target_node_id=target_node_id,
                         relationship_type=relationship_type,
                         constraint_name=constraint_name)
        result = svc.add_edge(req)
        return result.model_dump()

    @mcp_server.tool()
    async def designer_list_edges(diagram_id: str):
        """List all edges/relationships in a diagram."""
        results = svc.list_edges(diagram_id)
        return [r.model_dump() for r in results]

    @mcp_server.tool()
    async def designer_delete_edge(edge_id: str):
        """Delete a relationship edge."""
        success = svc.delete_edge(edge_id)
        return {"success": success}

    @mcp_server.tool()
    async def designer_reverse_engineer(connection_id: str,
                                         schema_name: str = "public",
                                         include_views: bool = True,
                                         create_diagram: bool = True,
                                         diagram_name: str = None):
        """Reverse engineer a database schema into a visual diagram."""
        req = ReverseEngineerRequest(
            connection_id=connection_id,
            schema_name=schema_name,
            include_views=include_views,
            create_diagram=create_diagram,
            diagram_name=diagram_name,
        )
        result = svc.reverse_engineer(req)
        return result.model_dump()

    @mcp_server.tool()
    async def designer_generate_ddl(diagram_id: str,
                                     include_drop: bool = False,
                                     include_if_not_exists: bool = True,
                                     schema_name: str = "public"):
        """Generate DDL from a diagram's nodes."""
        req = DDLGenerateRequest(
            diagram_id=diagram_id,
            include_drop=include_drop,
            include_if_not_exists=include_if_not_exists,
            schema_name=schema_name,
        )
        result = svc.generate_ddl(req)
        return result.model_dump()

    @mcp_server.tool()
    async def designer_compare(connection_id: str,
                                source_b_ref: str,
                                source_b_type: str = "diagram",
                                schema_name: str = "public"):
        """Compare a live database schema against a diagram."""
        req = CompareRequest(
            source_a_type="connection",
            source_a_ref=connection_id,
            source_b_type=source_b_type,
            source_b_ref=source_b_ref,
            schema_name=schema_name,
        )
        result = svc.compare(req)
        return result.model_dump()

    @mcp_server.tool()
    async def designer_synchronize(diagram_id: str, connection_id: str,
                                    schema_name: str = "public",
                                    mode: str = "ddl_only"):
        """Synchronize a diagram with a database (forward engineering)."""
        req = SyncRequest(
            diagram_id=diagram_id,
            connection_id=connection_id,
            schema_name=schema_name,
            mode=mode,
        )
        result = svc.synchronize(req)
        return result.model_dump()

    @mcp_server.tool()
    async def designer_list_templates(category: str = None,
                                       database_type: str = None):
        """List design templates."""
        results = svc.list_templates(category, database_type)
        return [r.model_dump() for r in results]

    @mcp_server.tool()
    async def designer_list_sync_history(diagram_id: str = None,
                                          connection_id: str = None):
        """List synchronization history."""
        results = svc.list_sync_history(diagram_id, connection_id)
        return [r.model_dump() for r in results]
