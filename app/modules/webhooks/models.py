"""
Webhook Manager — SQLModel DB Models

Persists webhook endpoint definitions and delivery logs to PostgreSQL.
Follows the same pattern as the Schema Builder module.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlmodel import SQLModel, Field, Column, JSON, Text
from sqlalchemy.sql import func
from sqlalchemy import DateTime


class WebhookEndpointRecord(SQLModel, table=True):
    """A webhook endpoint — inbound (receives events) or outbound (sends events)."""
    __tablename__ = "webhook_endpoints"

    id: str = Field(
        primary_key=True, max_length=128,
        description="Unique endpoint ID (e.g., wh_xxx)",
    )
    name: str = Field(
        max_length=256, index=True,
        description="Human-readable endpoint name",
    )
    description: Optional[str] = Field(
        default=None, sa_column=Column(Text),
    )
    url: str = Field(
        max_length=1024,
        description="Webhook URL (inbound: platform-generated, outbound: user-configured)",
    )
    secret: Optional[str] = Field(
        default=None, max_length=512,
        description="HMAC signing secret (auto-generated for inbound)",
    )
    enabled: bool = Field(default=True)
    direction: str = Field(
        max_length=16,
        description="inbound | outbound",
    )
    event_types: List[str] = Field(
        default_factory=list, sa_column=Column(JSON),
        description="List of event types this webhook subscribes to",
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, sa_column=Column(JSON),
        description="Custom HTTP headers for outbound webhook requests",
    )
    retry_config: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON),
        description="Retry configuration: max_retries, interval_seconds, backoff",
    )
    last_triggered_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True)),
    )
    metadata_json: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )


class WebhookDeliveryRecord(SQLModel, table=True):
    """A delivery log entry — tracks every webhook send/receive attempt."""
    __tablename__ = "webhook_deliveries"

    id: str = Field(
        primary_key=True, max_length=128,
        description="Unique delivery ID",
    )
    endpoint_id: str = Field(
        max_length=128, index=True,
        description="References webhook_endpoints.id",
    )
    endpoint_name: str = Field(
        max_length=256,
        description="Denormalized endpoint name for display",
    )
    direction: str = Field(
        max_length=16,
        description="inbound | outbound",
    )
    event_type: str = Field(
        max_length=128,
        description="The event that triggered this delivery",
    )
    status: str = Field(
        max_length=16, index=True,
        description="success | failed | pending | retrying",
    )
    request_url: Optional[str] = Field(
        default=None, max_length=1024,
    )
    request_headers: Optional[Dict[str, str]] = Field(
        default=None, sa_column=Column(JSON),
    )
    request_body: Optional[str] = Field(
        default=None, sa_column=Column(Text),
    )
    response_status: Optional[int] = Field(default=None)
    response_body: Optional[str] = Field(
        default=None, sa_column=Column(Text),
    )
    error: Optional[str] = Field(
        default=None, sa_column=Column(Text),
    )
    duration_ms: Optional[float] = Field(default=None)
    attempt: int = Field(default=1)
    max_attempts: int = Field(default=3)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
