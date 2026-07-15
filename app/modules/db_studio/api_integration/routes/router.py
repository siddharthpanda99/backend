"""Module 28 — API Layer, WebSocket & MCP Integration routes (thin wrappers)."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.api_integration.service import ApiIntegrationService
from common_lib.modules.db_studio.api_integration.schemas import (
    ApiKeyCreate, ApiKeyOut, ApiKeyFullOut,
    ApiClientCreate, ApiClientOut,
    WebhookSubscriptionCreate, WebhookSubscriptionUpdate, WebhookSubscriptionOut,
    WebSocketSessionOut,
    McpToolCreate, McpToolOut,
    McpResourceCreate, McpResourceOut,
    ApiUsageOut,
    ApiVersionCreate, ApiVersionOut,
    ApiIntegrationDashboardOut,
)

router = APIRouter(tags=["UDS — API Layer & MCP Integration"])
svc = ApiIntegrationService()


# ── API Keys ───────────────────────────────────────────────────

@router.post("/api-keys", response_model=ApiKeyFullOut)
def create_api_key(body: ApiKeyCreate):
    return svc.create_api_key(body)

@router.get("/api-keys", response_model=List[ApiKeyOut])
def list_api_keys(is_active: Optional[bool] = None, limit: int = 50):
    return svc.list_api_keys(is_active=is_active, limit=limit)

@router.put("/api-keys/{key_id}/revoke")
def revoke_api_key(key_id: str):
    if not svc.revoke_api_key(key_id):
        raise HTTPException(404, "API key not found")
    return {"ok": True}


# ── API Clients ────────────────────────────────────────────────

@router.post("/clients", response_model=ApiClientOut)
def create_client(body: ApiClientCreate):
    return svc.create_client(body)

@router.get("/clients", response_model=List[ApiClientOut])
def list_clients():
    return svc.list_clients()

@router.delete("/clients/{client_id}")
def delete_client(client_id: str):
    if not svc.delete_client(client_id):
        raise HTTPException(404, "Client not found")
    return {"ok": True}


# ── Webhooks ───────────────────────────────────────────────────

@router.post("/webhooks", response_model=WebhookSubscriptionOut)
def create_webhook(body: WebhookSubscriptionCreate):
    return svc.create_webhook(body)

@router.get("/webhooks", response_model=List[WebhookSubscriptionOut])
def list_webhooks(is_active: Optional[bool] = None):
    return svc.list_webhooks(is_active=is_active)

@router.put("/webhooks/{webhook_id}", response_model=Optional[WebhookSubscriptionOut])
def update_webhook(webhook_id: str, body: WebhookSubscriptionUpdate):
    result = svc.update_webhook(webhook_id, body)
    if not result:
        raise HTTPException(404, "Webhook not found")
    return result

@router.delete("/webhooks/{webhook_id}")
def delete_webhook(webhook_id: str):
    if not svc.delete_webhook(webhook_id):
        raise HTTPException(404, "Webhook not found")
    return {"ok": True}


# ── WebSocket Sessions ─────────────────────────────────────────

@router.post("/ws-sessions", response_model=WebSocketSessionOut)
def create_ws_session(session_id: str, connection_type: str = "websocket", user_id: Optional[str] = None):
    return svc.create_ws_session(session_id, connection_type, user_id)

@router.get("/ws-sessions", response_model=List[WebSocketSessionOut])
def list_ws_sessions(is_active: Optional[bool] = None, limit: int = 50):
    return svc.list_ws_sessions(is_active=is_active, limit=limit)

@router.put("/ws-sessions/{session_id}/close", response_model=Optional[WebSocketSessionOut])
def close_ws_session(session_id: str):
    result = svc.close_ws_session(session_id)
    if not result:
        raise HTTPException(404, "WebSocket session not found")
    return result


# ── MCP Tools ──────────────────────────────────────────────────

@router.post("/mcp-tools", response_model=McpToolOut)
def register_mcp_tool(body: McpToolCreate):
    return svc.register_mcp_tool(body)

@router.get("/mcp-tools", response_model=List[McpToolOut])
def list_mcp_tools(category: Optional[str] = None):
    return svc.list_mcp_tools(category=category)

@router.delete("/mcp-tools/{tool_id}")
def delete_mcp_tool(tool_id: str):
    if not svc.delete_mcp_tool(tool_id):
        raise HTTPException(404, "MCP tool not found")
    return {"ok": True}


# ── MCP Resources ──────────────────────────────────────────────

@router.post("/mcp-resources", response_model=McpResourceOut)
def register_mcp_resource(body: McpResourceCreate):
    return svc.register_mcp_resource(body)

@router.get("/mcp-resources", response_model=List[McpResourceOut])
def list_mcp_resources(resource_type: Optional[str] = None):
    return svc.list_mcp_resources(resource_type=resource_type)

@router.delete("/mcp-resources/{resource_id}")
def delete_mcp_resource(resource_id: str):
    if not svc.delete_mcp_resource(resource_id):
        raise HTTPException(404, "MCP resource not found")
    return {"ok": True}


# ── API Versions ───────────────────────────────────────────────

@router.post("/api-versions", response_model=ApiVersionOut)
def create_api_version(body: ApiVersionCreate):
    return svc.create_api_version(body)

@router.get("/api-versions", response_model=List[ApiVersionOut])
def list_api_versions():
    return svc.list_api_versions()


# ── Usage ──────────────────────────────────────────────────────

@router.post("/usage", response_model=ApiUsageOut)
def record_usage(endpoint: str, method: str, status_code: int = 200,
                 api_key_id: Optional[str] = None, duration_ms: Optional[int] = None):
    return svc.record_usage(endpoint, method, status_code, api_key_id, duration_ms)

@router.get("/usage", response_model=List[ApiUsageOut])
def list_usage(endpoint: Optional[str] = None, limit: int = 100):
    return svc.list_usage(endpoint=endpoint, limit=limit)


# ── Dashboard ──────────────────────────────────────────────────

@router.get("/dashboard", response_model=ApiIntegrationDashboardOut)
def api_dashboard():
    return svc.get_dashboard()


# ── Seed ───────────────────────────────────────────────────────

@router.post("/seed")
def seed_api_integration():
    count = svc.seed_defaults()
    return {"seeded": count}
