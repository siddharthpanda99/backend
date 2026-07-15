"""MCP tools for Connector SDK & Driver Framework (UDS Module 08)."""

import logging
logger = logging.getLogger(__name__)

def register_connector_sdk_tools(mcp_server):
    from common_lib.modules.db_studio.connector_sdk import (
        ConnectorSDKService, ConnectorCreate, DriverCreate,
        PluginRegister, CapabilityCreate, CertificationCreate,
    )
    svc = ConnectorSDKService()

    @mcp_server.tool()
    async def sdk_register_connector(name: str, database_type: str,
                                      connector_type: str = "sql",
                                      description: str = None):
        req = ConnectorCreate(name=name, database_type=database_type,
                              connector_type=connector_type, description=description)
        return svc.register_connector(req).model_dump()

    @mcp_server.tool()
    async def sdk_list_connectors(connector_type: str = None):
        results = svc.list_connectors(connector_type=connector_type)
        return [r.model_dump() for r in results]

    @mcp_server.tool()
    async def sdk_get_connector(connector_id: str):
        r = svc.get_connector(connector_id)
        return r.model_dump() if r else {"error": "Not found"}

    @mcp_server.tool()
    async def sdk_delete_connector(connector_id: str):
        return {"success": svc.delete_connector(connector_id)}

    @mcp_server.tool()
    async def sdk_register_driver(name: str, database_type: str,
                                   driver_type: str = "python_package",
                                   package_name: str = None):
        req = DriverCreate(name=name, database_type=database_type,
                           driver_type=driver_type, package_name=package_name)
        return svc.register_driver(req).model_dump()

    @mcp_server.tool()
    async def sdk_list_drivers(database_type: str = None):
        results = svc.list_drivers(database_type=database_type)
        return [r.model_dump() for r in results]

    @mcp_server.tool()
    async def sdk_register_plugin(name: str, plugin_type: str = "connector",
                                   description: str = None):
        req = PluginRegister(name=name, plugin_type=plugin_type, description=description)
        return svc.register_plugin(req).model_dump()

    @mcp_server.tool()
    async def sdk_list_plugins(plugin_type: str = None):
        results = svc.list_plugins(plugin_type=plugin_type)
        return [r.model_dump() for r in results]

    @mcp_server.tool()
    async def sdk_register_capability(connector_id: str, name: str,
                                       category: str = "execution", supported: bool = True):
        req = CapabilityCreate(connector_id=connector_id, name=name,
                               category=category, supported=supported)
        return svc.register_capability(req).model_dump()

    @mcp_server.tool()
    async def sdk_list_capabilities(connector_id: str = None):
        results = svc.list_capabilities(connector_id=connector_id)
        return [r.model_dump() for r in results]
