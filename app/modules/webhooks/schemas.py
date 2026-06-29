"""
Webhook Manager — Pydantic Schemas for API request/response validation.

Mirrors the frontend WebhookEndpoint and WebhookDelivery types
from webhookTypes.ts for seamless migration from seed data.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─── Endpoint Schemas ───────────────────────────────────────────────


class RetryConfig(BaseModel):
    max_retries: int = 3
    interval_seconds: int = 60
    backoff: str = "exponential"  # linear | exponential


class EndpointCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = None
    url: str = Field(..., max_length=1024)
    secret: Optional[str] = None
    enabled: bool = True
    direction: str = Field(..., pattern=r"^(inbound|outbound)$")
    event_types: List[str] = Field(default_factory=lambda: ["custom.event"])
    headers: Optional[Dict[str, str]] = None
    retry_config: Optional[RetryConfig] = None


class EndpointUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    secret: Optional[str] = None
    enabled: Optional[bool] = None
    direction: Optional[str] = None
    event_types: Optional[List[str]] = None
    headers: Optional[Dict[str, str]] = None
    retry_config: Optional[RetryConfig] = None


class EndpointResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    url: str
    secret: Optional[str] = None
    enabled: bool
    direction: str
    event_types: List[str] = []
    headers: Optional[Dict[str, str]] = None
    retry_config: Optional[Dict[str, Any]] = None
    last_triggered_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EndpointListResponse(BaseModel):
    items: List[EndpointResponse]
    total: int = 0


# ─── Delivery Schemas ───────────────────────────────────────────────


class DeliveryCreate(BaseModel):
    endpoint_id: str
    endpoint_name: str
    direction: str = Field("outbound", pattern=r"^(inbound|outbound)$")
    event_type: str
    status: str = "pending"
    request_url: Optional[str] = None
    request_headers: Optional[Dict[str, str]] = None
    request_body: Optional[str] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    attempt: int = 1
    max_attempts: int = 3


class DeliveryUpdate(BaseModel):
    status: Optional[str] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    attempt: Optional[int] = None


class DeliveryResponse(BaseModel):
    id: str
    endpoint_id: str
    endpoint_name: str
    direction: str
    event_type: str
    status: str
    request_url: Optional[str] = None
    request_headers: Optional[Dict[str, str]] = None
    request_body: Optional[str] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    attempt: int
    max_attempts: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DeliveryListResponse(BaseModel):
    items: List[DeliveryResponse]
    total: int = 0


# ─── Test Send Schemas ───────────────────────────────────────────────


class TestSendRequest(BaseModel):
    event_type: str = "test.event"
    payload: Optional[Dict[str, Any]] = None


class TestSendResponse(BaseModel):
    success: bool
    response_status: Optional[int] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None


# ─── Event-Workflow Mapping Schemas ─────────────────────────────────


class EventWorkflowMappingCreate(BaseModel):
    event_type: str = Field(..., max_length=256)
    workflow_id: str = Field(..., max_length=256)
    workflow_inputs: Optional[Dict[str, Any]] = None
    enabled: bool = True
    description: Optional[str] = None


class EventWorkflowMappingUpdate(BaseModel):
    event_type: Optional[str] = None
    workflow_id: Optional[str] = None
    workflow_inputs: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None


class EventWorkflowMappingResponse(BaseModel):
    id: str
    event_type: str
    workflow_id: str
    workflow_inputs: Optional[Dict[str, Any]] = None
    enabled: bool = True
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EventWorkflowMappingListResponse(BaseModel):
    items: List[EventWorkflowMappingResponse]
    total: int = 0


# ─── Webhook Callback Schemas ───────────────────────────────────────


class CallbackCreate(BaseModel):
    callback_url: str = Field(..., max_length=1024)
    status_url: Optional[str] = None
    secret: Optional[str] = None
    max_retries: int = 3
    ttl_seconds: Optional[int] = None


class CallbackUpdate(BaseModel):
    status: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CallbackResponse(BaseModel):
    id: str
    callback_url: str
    status_url: Optional[str] = None
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3

    class Config:
        from_attributes = True


# ─── Inbound Event Schemas ──────────────────────────────────────────


class InboundEventRequest(BaseModel):
    event_type: str = Field(..., max_length=256)
    payload: Dict[str, Any] = Field(default_factory=dict)
    headers: Optional[Dict[str, str]] = None
    timestamp: Optional[str] = None


class InboundEventResponse(BaseModel):
    success: bool = True
    event_id: str
    workflows_triggered: int = 0
    message: str = "Event received"
    error: Optional[str] = None


# ─── Common ─────────────────────────────────────────────────────────


class APIResponse(BaseModel):
    success: bool = True
    data: Optional[Any] = None
    message: str = "OK"
    error: Optional[str] = None
