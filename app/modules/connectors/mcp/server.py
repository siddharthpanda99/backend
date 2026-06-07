"""MCP server implementation for connector exposure.

Agents discover connectors and invoke tools through this interface.
The MCP layer translates between tool definitions and the standard
tool format expected by AI frameworks.
"""

import importlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from common_lib.modules.plugins.connectors.registry import get_connector_registry
from common_lib.modules.plugins.connectors.models.db import ConnectorRecord
from common_lib.modules.data_storage.database.connection import get_session
from sqlmodel import select
from app.modules.connectors.providers import get_provider, get_registered_ids

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp/connectors", tags=["MCP-Connectors"])


# ---------------------------------------------------------------------------
# Provider endpoint extraction
# ---------------------------------------------------------------------------

_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")


def _generate_schema_from_path(path: str) -> Dict[str, Any]:
    """Auto-generate a JSON Schema from URL path parameters.

    Extracts {param_name} placeholders and creates a minimal
    input_schema with string-typed required parameters.
    """
    params = _PATH_PARAM_RE.findall(path)
    if not params:
        return {"type": "object", "properties": {}, "required": []}

    properties = {}
    for p in params:
        # Derive a human-readable description (specific patterns before generic underscore replace)
        readable = p.replace("id_or_key", "ID or key").replace("_id", " ID").replace("_uuid", " UUID").replace("_slug", " slug").replace("_", " ")
        properties[p] = {
            "type": "string",
            "description": f"{readable}",
        }

    return {
        "type": "object",
        "properties": properties,
        "required": list(params),
    }


_FALLBACK_ENDPOINTS: Optional[Dict[str, Any]] = None


def _get_fallback_endpoints() -> Dict[str, Dict[str, Any]]:
    """Load the TOOL_ENDPOINTS from execute_engine as the third fallback pattern.

    These cover connectors without dedicated provider modules
    (Stripe, Twilio, SendGrid, PayPal, AWS, GCP, Azure, etc.).
    """
    global _FALLBACK_ENDPOINTS
    if _FALLBACK_ENDPOINTS is not None:
        return _FALLBACK_ENDPOINTS

    from app.modules.connectors.execute_engine import TOOL_ENDPOINTS

    _FALLBACK_ENDPOINTS = {}
    for tool_id, (method, path) in TOOL_ENDPOINTS.items():
        _FALLBACK_ENDPOINTS[tool_id] = {
            "tool_id": tool_id,
            "http_method": method,
            "url_path": path,
            "input_schema": _generate_schema_from_path(path),
            "source": "fallback",
        }
    return _FALLBACK_ENDPOINTS


def _extract_provider_endpoints(provider_id: str) -> Dict[str, Dict[str, Any]]:
    """Extract all endpoint definitions from a connector provider.

    Handles two patterns:
    1. Module-level dicts ending in _ENDPOINTS (e.g., JIRA_ENDPOINTS, CONFLUENCE_ENDPOINTS)
    2. Provider class 'endpoints' attribute (RESTProvider pattern)

    Returns a dict mapping tool_id -> {http_method, url_path, input_schema, source}
    """
    endpoints: Dict[str, Dict[str, Any]] = {}

    # Pattern 1: Module-level _ENDPOINTS dicts (e.g. Atlassian provider)
    try:
        provider_module = importlib.import_module(
            f"app.modules.connectors.providers.{provider_id}.provider"
        )
        for attr_name in dir(provider_module):
            if attr_name.endswith("_ENDPOINTS") and attr_name != "ATLASSIAN_ENDPOINTS":
                ep_dict = getattr(provider_module, attr_name, None)
                if isinstance(ep_dict, dict):
                    product = attr_name.replace("_ENDPOINTS", "").lower()
                    for tool_id, (method, path) in ep_dict.items():
                        if tool_id not in endpoints:
                            endpoints[tool_id] = {
                                "tool_id": tool_id,
                                "http_method": method,
                                "url_path": path,
                                "input_schema": _generate_schema_from_path(path),
                                "source": f"{provider_id}/{product}",
                            }
    except (ImportError, AttributeError, Exception) as e:
        logger.debug(f"No module-level endpoints for provider '{provider_id}': {e}")

    # Pattern 2: Provider class 'endpoints' attribute (RESTProvider pattern)
    try:
        provider_cls = get_provider(provider_id)
        if provider_cls and hasattr(provider_cls, "endpoints"):
            ep_dict = getattr(provider_cls, "endpoints")
            if isinstance(ep_dict, dict):
                for tool_id, (method, path) in ep_dict.items():
                    if tool_id not in endpoints:
                        endpoints[tool_id] = {
                            "tool_id": tool_id,
                            "http_method": method,
                            "url_path": path,
                            "input_schema": _generate_schema_from_path(path),
                            "source": f"{provider_id}/class",
                        }
    except Exception as e:
        logger.debug(f"No class-level endpoints for provider '{provider_id}': {e}")

    return endpoints


@router.get("/tools/list")
async def mcp_list_tools(
    connector_id: Optional[str] = None,
    search: Optional[str] = None,
    tag: Optional[str] = None,
):
    """List all available connector tools in MCP format.

    Returns tool definitions formatted for AI agent consumption.
    Each tool includes name, description, input_schema, and
    the connector_id it belongs to.
    """
    registry = get_connector_registry()
    tools = []

    if connector_id:
        try:
            connector = registry.get(connector_id)
            connector_tools = connector.tools
            if search:
                sl = search.lower()
                connector_tools = [
                    t
                    for t in connector_tools
                    if sl in t.name.lower() or sl in t.description.lower()
                ]
            if tag:
                connector_tools = [t for t in connector_tools if tag in t.tags]
            for t in connector_tools:
                tools.append(_tool_to_mcp(t, connector_id))
        except Exception:
            raise HTTPException(
                status_code=404, detail=f"Connector '{connector_id}' not found"
            )
    else:
        for connector in registry.list():
            connector_tools = connector.tools
            if search:
                sl = search.lower()
                connector_tools = [
                    t
                    for t in connector_tools
                    if sl in t.name.lower() or sl in t.description.lower()
                ]
            if tag:
                connector_tools = [t for t in connector_tools if tag in t.tags]
            for t in connector_tools:
                tools.append(_tool_to_mcp(t, connector.id))

    return {
        "tools": tools,
        "total": len(tools),
    }


@router.get("/tools/{tool_id}")
async def mcp_get_tool(tool_id: str):
    """Get a specific tool definition in MCP format."""
    registry = get_connector_registry()
    try:
        tool = registry.get_tool(tool_id)
        connector = registry.find_connector_by_tool(tool_id)
        connector_id = connector.id if connector else "unknown"
        return _tool_to_mcp(tool, connector_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/connectors/list")
async def mcp_list_connectors():
    """List all available connectors in MCP format."""
    registry = get_connector_registry()
    connectors = []
    for c in registry.list():
        connectors.append(
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "version": c.version,
                "status": c.status.value,
                "auth_schemes": [s.type.value for s in c.auth_schemes],
                "tool_count": len(c.tools),
                "categories": c.metadata.categories,
                "tags": c.metadata.tags,
                "docs_url": c.metadata.docs_url,
                "logo_url": c.metadata.logo_url,
            }
        )
    return {"connectors": connectors, "total": len(connectors)}


@router.get("/connectors/{connector_id}")
async def mcp_get_connector(connector_id: str):
    """Get a specific connector with all its tools."""
    registry = get_connector_registry()
    try:
        c = registry.get(connector_id)
        return {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "version": c.version,
            "status": c.status.value,
            "auth_schemes": [s.type.value for s in c.auth_schemes],
            "tools": [_tool_to_mcp(t, c.id) for t in c.tools],
            "categories": c.metadata.categories,
            "tags": c.metadata.tags,
            "docs_url": c.metadata.docs_url,
            "logo_url": c.metadata.logo_url,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))



@router.get("/provider-endpoints")
async def mcp_connector_provider_endpoints(
    connector_id: Optional[str] = None,
    search: Optional[str] = None,
    include_schema: bool = True,
    include_fallback: bool = True,
):
    """List ALL endpoint definitions from ALL connector providers.

    This is the authoritative source for every REST API endpoint each
    connector provider exposes. Unlike /tools/list (which returns only
    what's seeded in the DB), this returns the actual provider endpoint
    registries with raw HTTP method + URL path templates.

    Use this to:
    - Discover every API capability a connector offers
    - Build MCP tool definitions for AI agents
    - Find the exact REST endpoint for a given tool_id

    Returns endpoints grouped by provider/connector_id.
    """
    provider_ids = get_registered_ids()
    result: Dict[str, Any] = {}
    total_endpoints = 0
    seen_tool_ids: set = set()

    for pid in sorted(provider_ids):
        if connector_id and pid != connector_id:
            continue

        endpoints = _extract_provider_endpoints(pid)
        if not endpoints:
            continue

        provider_cls = get_provider(pid)
        display_name = getattr(provider_cls, "display_name", pid.title()) if provider_cls else pid.title()

        endpoint_list = list(endpoints.values())

        # Track all tool_ids from dedicated providers for fallback dedup
        for e in endpoint_list:
            seen_tool_ids.add(e["tool_id"])

        # Apply search filter (match both tool_id and url_path)
        if search:
            sl = search.lower()
            endpoint_list = [
                e for e in endpoint_list
                if sl in e["tool_id"].lower() or sl in e["url_path"].lower()
            ]

        # Build endpoint entries, optionally excluding schema
        if include_schema:
            clean_endpoints = endpoint_list
        else:
            clean_endpoints = [
                {k: v for k, v in e.items() if k != "input_schema"}
                for e in endpoint_list
            ]

        result[pid] = {
            "provider_id": pid,
            "display_name": display_name,
            "endpoint_count": len(clean_endpoints),
            "endpoints": clean_endpoints,
        }
        total_endpoints += len(clean_endpoints)

    # Include fallback endpoints for connectors without dedicated providers
    # Automatically deduped against tool_ids already seen in provider groups
    if include_fallback:
        fallback = _get_fallback_endpoints()
        fallback_list = [
            e for e in fallback.values()
            if e["tool_id"] not in seen_tool_ids
        ]

        if search:
            sl = search.lower()
            fallback_list = [
                e for e in fallback_list
                if sl in e["tool_id"].lower() or sl in e["url_path"].lower()
            ]

        if include_schema:
            clean_fallback = fallback_list
        else:
            clean_fallback = [
                {k: v for k, v in e.items() if k != "input_schema"}
                for e in fallback_list
            ]

        if clean_fallback:
            result["__fallback__"] = {
                "provider_id": "__fallback__",
                "display_name": "Fallback/Generic",
                "description": "Endpoints from connectors without dedicated providers (Stripe, Twilio, AWS, GCP, Azure, GitLab, Linear, etc.). Automatically deduped against provider endpoints.",
                "endpoint_count": len(clean_fallback),
                "endpoints": clean_fallback,
            }
            total_endpoints += len(clean_fallback)

    return {
        "providers": result,
        "total_providers": len(result),
        "total_endpoints": total_endpoints,
        "query": {
            "connector_id": connector_id,
            "search": search,
        },
    }


def _tool_to_mcp(tool: Any, connector_id: str) -> Dict[str, Any]:
    """Convert a ToolDef to MCP agent-consumable format."""
    return {
        "id": tool.id,
        "connector_id": connector_id,
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.input_schema,
        "output_schema": tool.output_schema,
        "tags": tool.tags,
        "timeout_seconds": tool.timeout_seconds,
        "execution_mode": tool.execution_mode,
        "cacheable": tool.cacheable,
        "idempotent": tool.idempotent,
        "requires_approval": tool.requires_approval,
        "deprecated": tool.deprecated,
    }
