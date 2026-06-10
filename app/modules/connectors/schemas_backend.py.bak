"""Pydantic schemas for connectors API."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Connector Schemas
# =============================================================================


class ConnectorCreate(BaseModel):
    id: str = Field(description="Unique connector ID (e.g. 'github')")
    name: str = Field(description="Display name")
    description: Optional[str] = None
    version: str = "1.0.0"
    status: str = "active"
    auth_schemes: List[Dict[str, Any]] = []
    tools: List[Dict[str, Any]] = []
    form_schema: Optional[Dict[str, Any]] = None
    connection_form_schema: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    tags: List[str] = []
    categories: List[str] = []

    model_config = {"from_attributes": True}


class ConnectorUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None
    auth_schemes: Optional[List[Dict[str, Any]]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    form_schema: Optional[Dict[str, Any]] = None
    connection_form_schema: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None

    model_config = {"from_attributes": True}


class ConnectorResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    version: str
    status: str
    auth_schemes: List[Dict[str, Any]] = []
    tools: List[Dict[str, Any]] = []
    form_schema: Optional[Dict[str, Any]] = None
    connection_form_schema: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    tags: List[str] = []
    categories: List[str] = []
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None

    model_config = {"from_attributes": True}


class ConnectorListResponse(BaseModel):
    items: List[ConnectorResponse]
    total: int


# =============================================================================
# Connection Schemas
# =============================================================================


class ConnectionCreate(BaseModel):
    connector_id: str
    auth_scheme: str = "api_key"
    label: str = ""
    form_data: Optional[Dict[str, Any]] = None
    key_id: Optional[int] = None
    metadata_json: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class ConnectionUpdate(BaseModel):
    label: Optional[str] = None
    auth_scheme: Optional[str] = None
    form_data: Optional[Dict[str, Any]] = None
    key_id: Optional[int] = None
    status: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class ConnectionResponse(BaseModel):
    id: str
    connector_id: str
    user_id: str
    auth_scheme: str
    key_id: Optional[int] = None
    status: str
    label: str
    form_data: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None
    expires_at: Optional[Any] = None

    model_config = {"from_attributes": True}


class ConnectionListResponse(BaseModel):
    items: List[ConnectionResponse]
    total: int


# =============================================================================
# Execution Schemas
# =============================================================================


class ToolExecuteRequest(BaseModel):
    connection_id: str
    tool_id: str
    params: Dict[str, Any] = {}
    override_base_url: Optional[str] = Field(
        default=None,
        description="Optional base URL override. If set, overrides the connection's instance_url for this execution.",
    )
    query_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional query parameters to append to the request URL.",
    )


class ToolExecuteResponse(BaseModel):
    id: Optional[str] = None
    status: str
    result: Any = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    http_status: Optional[int] = Field(
        default=None,
        description="HTTP status code from the target API (e.g. 200, 404)",
    )
    response_headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Response headers from the target API",
    )


# =============================================================================
# Execution History Schemas
# =============================================================================


class ExecutionHistoryResponse(BaseModel):
    id: str
    connection_id: str
    connector_id: str
    tool_id: str
    params: Optional[Any] = None
    result: Optional[Any] = None
    status: str
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None
    created_at: Optional[Any] = None

    model_config = {"from_attributes": True}


class ExecutionHistoryListResponse(BaseModel):
    items: List[ExecutionHistoryResponse]
    total: int


# =============================================================================
# Connection Audit / Changelog Schemas
# =============================================================================


class AuditEntryResponse(BaseModel):
    id: str
    connection_id: str
    action: str
    changed_by: str
    summary: Optional[str] = None
    diff: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: Optional[Any] = None

    model_config = {"from_attributes": True}


class AuditListResponse(BaseModel):
    items: List[AuditEntryResponse]
    total: int


# =============================================================================
# Test Connection Schema
# =============================================================================


class ConnectionTestResponse(BaseModel):
    status: str
    message: str
    latency_ms: Optional[float] = None
