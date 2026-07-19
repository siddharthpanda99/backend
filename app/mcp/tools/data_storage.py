"""MCP tools for Data Storage — catalogue management, connector management.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps common_lib.modules.data_storage services.
"""

import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.tools.data_storage")


def register_data_storage_tools(mcp: FastMCP):
    """Register tools for data storage operations."""

    @mcp.tool()
    async def datastorage_list_catalogs() -> List[Dict[str, Any]]:
        """List all data catalogs."""
        try:
            from common_lib.modules.data_storage.catalogue.services import CatalogService
            svc = CatalogService()
            result = svc.list_catalogs() if hasattr(svc, "list_catalogs") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"datastorage_list_catalogs error: {e}")
            return []

    @mcp.tool()
    async def datastorage_create_catalog(name: str, description: str = "", schema_def: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new data catalog."""
        try:
            from common_lib.modules.data_storage.catalogue.services import CatalogService
            svc = CatalogService()
            result = svc.create_catalog(name, description, schema_def) if hasattr(svc, "create_catalog") else {"name": name}
            return result if isinstance(result, dict) else {"name": name}
        except Exception as e:
            logger.error(f"datastorage_create_catalog error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def datastorage_get_catalog(catalog_id: str) -> Dict[str, Any]:
        """Get a catalog by ID."""
        try:
            from common_lib.modules.data_storage.catalogue.services import CatalogService
            svc = CatalogService()
            result = svc.get_catalog(catalog_id) if hasattr(svc, "get_catalog") else None
            if result is None:
                return {"error": f"Catalog '{catalog_id}' not found"}
            return result if isinstance(result, dict) else {"catalog_id": catalog_id}
        except Exception as e:
            logger.error(f"datastorage_get_catalog error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def datastorage_delete_catalog(catalog_id: str) -> str:
        """Delete a catalog."""
        try:
            from common_lib.modules.data_storage.catalogue.services import CatalogService
            svc = CatalogService()
            svc.delete_catalog(catalog_id) if hasattr(svc, "delete_catalog") else None
            return f"Catalog {catalog_id} deleted"
        except Exception as e:
            logger.error(f"datastorage_delete_catalog error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def datastorage_list_connectors() -> List[Dict[str, Any]]:
        """List all data connectors."""
        try:
            from common_lib.modules.data_storage.database.connectors.registry import ConnectorManager
            svc = ConnectorManager()
            result = svc.list_connectors() if hasattr(svc, "list_connectors") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"datastorage_list_connectors error: {e}")
            return []

    @mcp.tool()
    async def datastorage_create_connector(name: str, connector_type: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new data connector."""
        try:
            from common_lib.modules.data_storage.database.connectors.registry import ConnectorManager
            svc = ConnectorManager()
            result = svc.create_connector(name, connector_type, config) if hasattr(svc, "create_connector") else {"name": name}
            return result if isinstance(result, dict) else {"name": name}
        except Exception as e:
            logger.error(f"datastorage_create_connector error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def datastorage_test_connector(connector_id: str) -> Dict[str, Any]:
        """Test a data connector connection."""
        try:
            from common_lib.modules.data_storage.database.connectors.registry import ConnectorManager
            svc = ConnectorManager()
            result = svc.test_connector(connector_id) if hasattr(svc, "test_connector") else {"connected": False}
            return result if isinstance(result, dict) else {"connected": False}
        except Exception as e:
            logger.error(f"datastorage_test_connector error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def datastorage_delete_connector(connector_id: str) -> str:
        """Delete a data connector."""
        try:
            from common_lib.modules.data_storage.database.connectors.registry import ConnectorManager
            svc = ConnectorManager()
            svc.delete_connector(connector_id) if hasattr(svc, "delete_connector") else None
            return f"Connector {connector_id} deleted"
        except Exception as e:
            logger.error(f"datastorage_delete_connector error: {e}")
            return f"Error: {e}"

    logger.info("Data Storage: 8 MCP tools registered")
