"""
Connection Health — Pydantic Schemas

Matches the frontend HealthConnection interface from ConnectionHealthPanel.tsx
for seamless migration from mock data to real API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─── Health Check Result ────────────────────────────────────────────

class HealthCheckSnapshot(BaseModel):
    """A single health check result."""
    id: str
    connection_id: str
    status: str
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None
    checked_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Health Connection (matches frontend HealthConnection interface) ─

class ErrorEntry(BaseModel):
    timestamp: str
    message: str


class HealthConnectionResponse(BaseModel):
    """Aggregated health data for a single connection, matching frontend interface."""
    id: str
    name: str
    type: str
    status: str  # healthy | degraded | down | untested
    latency_history: List[float] = []
    uptime_pct: float = 100.0
    avg_response_ms: float = 0.0
    error_rate_pct: float = 0.0
    last_tested: Optional[str] = None
    last_errors: List[ErrorEntry] = []


class HealthSummaryResponse(BaseModel):
    """Aggregated health summary across all connections."""
    total: int = 0
    healthy: int = 0
    degraded: int = 0
    down: int = 0
    untested: int = 0
    connections: List[HealthConnectionResponse] = []


class RefreshResponse(BaseModel):
    success: bool = True
    tested: int = 0
    failed: int = 0
    message: str = "Health check complete"
    results: List[Dict[str, Any]] = []


# ─── Health Check Settings ─────────────────────────────────────────

class HealthSettingsResponse(BaseModel):
    id: str = "default"
    check_interval_seconds: int = 60
    auto_disable: bool = True
    failure_threshold: int = 3
    alert_threshold_ms: int = 200
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


class HealthSettingsUpdate(BaseModel):
    check_interval_seconds: Optional[int] = Field(None, ge=0, le=86400)
    auto_disable: Optional[bool] = None
    failure_threshold: Optional[int] = Field(None, ge=1, le=100)
    alert_threshold_ms: Optional[int] = Field(None, ge=0, le=30000)


# ─── Common ─────────────────────────────────────────────────────────

class APIResponse(BaseModel):
    success: bool = True
    data: Optional[Any] = None
    message: str = "OK"
    error: Optional[str] = None
