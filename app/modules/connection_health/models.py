"""
Connection Health — SQLModel DB Models

Persists health check snapshots (latency, status, error logs) for every
connection. Enables uptime tracking, latency history, and alert threshold
monitoring.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlmodel import SQLModel, Field, Column, JSON, Text
from sqlalchemy.sql import func
from sqlalchemy import DateTime


class ConnectionHealthRecord(SQLModel, table=True):
    """A single health check result snapshot for a connection."""
    __tablename__ = "connection_health"
    __table_args__ = {"extend_existing": True}

    id: str = Field(
        primary_key=True, max_length=128,
        description="Unique health check ID",
    )
    connection_id: str = Field(
        max_length=128, index=True,
        description="References ConnectionRecord.id",
    )
    connection_name: str = Field(
        max_length=256,
        description="Denormalized connection label for display",
    )
    connection_type: str = Field(
        max_length=128,
        description="Connector type (e.g. PostgreSQL, Redis, REST)",
    )
    status: str = Field(
        max_length=16, index=True,
        description="healthy | degraded | down | untested",
    )
    latency_ms: Optional[float] = Field(default=None)
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))
    duration_ms: Optional[float] = Field(default=None)
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )


class ConnectionHealthConfig(SQLModel, table=True):
    """Global health check configuration (singleton row)."""
    __tablename__ = "connection_health_config"
    __table_args__ = {"extend_existing": True}

    id: str = Field(primary_key=True, default="default", max_length=32)
    check_interval_seconds: int = Field(default=60)
    auto_disable: bool = Field(default=True)
    failure_threshold: int = Field(default=3)
    alert_threshold_ms: int = Field(default=200)
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
