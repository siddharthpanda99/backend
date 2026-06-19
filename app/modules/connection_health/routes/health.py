"""
Connection Health — Health Check Routes

/api/v1/connection-health — aggregated health summary, per-connection detail,
on-demand refresh (actual connection tests via ConnectionService), and settings.
"""

import uuid
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.plugins.connectors.models.db import ConnectionRecord
from common_lib.modules.connectors.connection_service import ConnectionService
from common_lib.modules.connectors.schemas import ConnectionListResponse
from common_lib.modules.exceptions import NotFoundError

from ..models import ConnectionHealthRecord, ConnectionHealthConfig
from ..schemas import (
    HealthConnectionResponse, HealthSummaryResponse, RefreshResponse,
    HealthSettingsResponse, HealthSettingsUpdate, APIResponse,
    ErrorEntry,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/connection-health", tags=["Connection Health"])


def _get_or_create_settings(db: Session) -> ConnectionHealthConfig:
    """Get the singleton health config, creating it if missing."""
    config = db.execute(
        select(ConnectionHealthConfig).where(ConnectionHealthConfig.id == "default")
    ).scalar_one_or_none()
    if not config:
        config = ConnectionHealthConfig(id="default")
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("/", response_model=HealthSummaryResponse)
async def get_health_summary(
    db: Session = Depends(get_session),
):
    """
    Get aggregated health summary for all connections.
    Returns computed status, latency history, uptime % based on
    stored health check snapshots from previous tests.
    """
    config = _get_or_create_settings(db)
    threshold_ms = config.alert_threshold_ms

    # Fetch all connections
    connections = db.execute(
        select(ConnectionRecord).order_by(ConnectionRecord.updated_at.desc())
    ).scalars().all()

    health_connections = []
    total = len(connections)
    healthy_count = 0
    degraded_count = 0
    down_count = 0
    untested_count = 0

    for conn in connections:
        # Fetch recent health snapshots for this connection
        snapshots = db.execute(
            select(ConnectionHealthRecord)
            .where(ConnectionHealthRecord.connection_id == conn.id)
            .order_by(ConnectionHealthRecord.checked_at.desc())
            .limit(24)  # last 24 check results
        ).scalars().all()

        # Build latency history from snapshots (oldest first for sparkline)
        latency_history = [s.latency_ms for s in reversed(snapshots) if s.latency_ms is not None]

        # Compute aggregated metrics
        total_checks = len(snapshots)
        failed_checks = sum(1 for s in snapshots if s.status in ("down", "degraded"))
        avg_latency = sum(latency_history) / len(latency_history) if latency_history else 0
        uptime_pct = ((total_checks - failed_checks) / total_checks * 100) if total_checks > 0 else (100 if conn.status == "active" else 0)
        error_rate_pct = (failed_checks / total_checks * 100) if total_checks > 0 else 0

        # Determine current status
        latest = snapshots[0] if snapshots else None
        if latest:
            status = latest.status
        elif conn.status == "active":
            status = "healthy"
        elif conn.status == "failed":
            status = "down"
        else:
            status = "untested"

        # Build error entries from failed snapshots
        last_errors = []
        for s in snapshots:
            if s.error_message and len(last_errors) < 5:
                last_errors.append(ErrorEntry(
                    timestamp=s.checked_at.isoformat() if s.checked_at else "",
                    message=s.error_message[:200],
                ))

        # Count status
        if status == "healthy":
            healthy_count += 1
        elif status == "degraded":
            degraded_count += 1
        elif status == "down":
            down_count += 1
        else:
            untested_count += 1

        # Get connector type from connector_id
        conn_type = conn.connector_id.capitalize() if conn.connector_id else "Unknown"

        health_connections.append(HealthConnectionResponse(
            id=conn.id,
            name=conn.label or conn.connector_id,
            type=conn_type,
            status=status,
            latency_history=latency_history,
            uptime_pct=round(uptime_pct, 1),
            avg_response_ms=round(avg_latency, 1),
            error_rate_pct=round(error_rate_pct, 1),
            last_tested=latest.checked_at.isoformat() if latest and latest.checked_at else (
                conn.updated_at.isoformat() if hasattr(conn, 'updated_at') and conn.updated_at else None
            ),
            last_errors=last_errors,
        ))

    return HealthSummaryResponse(
        total=total,
        healthy=healthy_count,
        degraded=degraded_count,
        down=down_count,
        untested=untested_count,
        connections=health_connections,
    )


@router.get("/{connection_id}", response_model=HealthConnectionResponse)
async def get_connection_health(
    connection_id: str,
    db: Session = Depends(get_session),
):
    """Get detailed health data for a single connection."""
    # First verify the connection exists
    try:
        conn_resp = ConnectionService.get_connection(connection_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")

    config = _get_or_create_settings(db)

    snapshots = db.execute(
        select(ConnectionHealthRecord)
        .where(ConnectionHealthRecord.connection_id == connection_id)
        .order_by(ConnectionHealthRecord.checked_at.desc())
        .limit(24)
    ).scalars().all()

    latency_history = [s.latency_ms for s in reversed(snapshots) if s.latency_ms is not None]

    total_checks = len(snapshots)
    failed_checks = sum(1 for s in snapshots if s.status in ("down", "degraded"))
    avg_latency = sum(latency_history) / len(latency_history) if latency_history else 0
    uptime_pct = ((total_checks - failed_checks) / total_checks * 100) if total_checks > 0 else (
        100 if conn_resp.status == "active" else 0
    )
    error_rate_pct = (failed_checks / total_checks * 100) if total_checks > 0 else 0

    latest = snapshots[0] if snapshots else None
    if latest:
        status = latest.status
    elif conn_resp.status == "active":
        status = "healthy"
    elif conn_resp.status == "failed":
        status = "down"
    else:
        status = "untested"

    last_errors = []
    for s in snapshots:
        if s.error_message and len(last_errors) < 5:
            last_errors.append(ErrorEntry(
                timestamp=s.checked_at.isoformat() if s.checked_at else "",
                message=s.error_message[:200],
            ))

    return HealthConnectionResponse(
        id=conn_resp.id,
        name=conn_resp.label or conn_resp.connector_id,
        type=conn_resp.connector_id.capitalize() if conn_resp.connector_id else "Unknown",
        status=status,
        latency_history=latency_history,
        uptime_pct=round(uptime_pct, 1),
        avg_response_ms=round(avg_latency, 1),
        error_rate_pct=round(error_rate_pct, 1),
        last_tested=latest.checked_at.isoformat() if latest and latest.checked_at else None,
        last_errors=last_errors,
    )


# ─── Refresh ───────────────────────────────────────────────────────


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_all_health(
    db: Session = Depends(get_session),
):
    """
    Run health checks on ALL connections.
    Tests each connection via ConnectionService.test_connection(),
    records the result as a health snapshot, and updates status metrics.
    """
    connections = db.execute(
        select(ConnectionRecord).order_by(ConnectionRecord.updated_at.desc())
    ).scalars().all()

    results = []
    tested = 0
    failed = 0

    for conn in connections:
        start = time.monotonic()
        try:
            resp = ConnectionService.test_connection(conn.id)

            duration = (time.monotonic() - start) * 1000
            latency = resp.latency_ms if hasattr(resp, 'latency_ms') and resp.latency_ms else duration
            status = "healthy"

            snapshot = ConnectionHealthRecord(
                id=str(uuid.uuid4()),
                connection_id=conn.id,
                connection_name=conn.label or conn.connector_id,
                connection_type=conn.connector_id.capitalize() if conn.connector_id else "Unknown",
                status=status,
                latency_ms=round(latency, 1),
                duration_ms=round(duration, 1),
            )
            db.add(snapshot)
            tested += 1
            results.append({
                "connection_id": conn.id,
                "status": status,
                "latency_ms": round(latency, 1),
            })

        except Exception as e:
            duration = (time.monotonic() - start) * 1000
            error_msg = str(e)[:500]

            snapshot = ConnectionHealthRecord(
                id=str(uuid.uuid4()),
                connection_id=conn.id,
                connection_name=conn.label or conn.connector_id,
                connection_type=conn.connector_id.capitalize() if conn.connector_id else "Unknown",
                status="down",
                latency_ms=None,
                error_message=error_msg,
                duration_ms=round(duration, 1),
            )
            db.add(snapshot)
            failed += 1
            results.append({
                "connection_id": conn.id,
                "status": "down",
                "error": error_msg,
            })

        # Prune old snapshots (keep last 100 per connection)
        old_snapshots = db.execute(
            select(ConnectionHealthRecord)
            .where(ConnectionHealthRecord.connection_id == conn.id)
            .order_by(ConnectionHealthRecord.checked_at.desc())
            .offset(100)
        ).scalars().all()
        for old in old_snapshots:
            db.delete(old)

    db.commit()

    return RefreshResponse(
        success=failed == 0 or tested > 0,
        tested=tested,
        failed=failed,
        message=f"Health check complete: {tested} tested, {failed} failed" if tested > 0 else "No connections to test",
        results=results,
    )


@router.post("/{connection_id}/refresh", response_model=RefreshResponse)
async def refresh_connection_health(
    connection_id: str,
    db: Session = Depends(get_session),
):
    """Run a health check on a single connection."""
    try:
        conn_resp = ConnectionService.get_connection(connection_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Re-fetch the DB record
    conn = db.execute(
        select(ConnectionRecord).where(ConnectionRecord.id == connection_id)
    ).scalar_one_or_none()

    start = time.monotonic()
    try:
        resp = ConnectionService.test_connection(connection_id)

        duration = (time.monotonic() - start) * 1000
        latency = resp.latency_ms if hasattr(resp, 'latency_ms') and resp.latency_ms else duration
        status = "healthy"

        snapshot = ConnectionHealthRecord(
            id=str(uuid.uuid4()),
            connection_id=conn.id,
            connection_name=conn.label or conn.connector_id,
            connection_type=conn.connector_id.capitalize() if conn.connector_id else "Unknown",
            status=status,
            latency_ms=round(latency, 1),
            duration_ms=round(duration, 1),
        )
        db.add(snapshot)
        db.commit()

        return RefreshResponse(
            success=True,
            tested=1,
            failed=0,
            message=f"Health check passed for '{conn.label or conn.connector_id}'",
            results=[{"connection_id": connection_id, "status": status, "latency_ms": round(latency, 1)}],
        )

    except Exception as e:
        duration = (time.monotonic() - start) * 1000
        error_msg = str(e)[:500]

        snapshot = ConnectionHealthRecord(
            id=str(uuid.uuid4()),
            connection_id=conn.id if conn else connection_id,
            connection_name=conn.label if conn else connection_id,
            connection_type=conn.connector_id.capitalize() if conn and conn.connector_id else "Unknown",
            status="down",
            latency_ms=None,
            error_message=error_msg,
            duration_ms=round(duration, 1),
        )
        db.add(snapshot)
        db.commit()

        return RefreshResponse(
            success=False,
            tested=0,
            failed=1,
            message=f"Health check failed: {error_msg[:200]}",
            results=[{"connection_id": connection_id, "status": "down", "error": error_msg}],
        )


# ─── Settings ──────────────────────────────────────────────────────


@router.get("/settings", response_model=HealthSettingsResponse)
async def get_health_settings(
    db: Session = Depends(get_session),
):
    """Get health check configuration settings."""
    config = _get_or_create_settings(db)
    return HealthSettingsResponse.model_validate(config)


@router.put("/settings", response_model=HealthSettingsResponse)
async def update_health_settings(
    data: HealthSettingsUpdate,
    db: Session = Depends(get_session),
):
    """Update health check configuration settings."""
    config = _get_or_create_settings(db)

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(config, key, value)

    from datetime import datetime, timezone
    config.last_updated = datetime.now(timezone.utc)

    db.commit()
    db.refresh(config)
    logger.info(f"Health check settings updated: {update_dict}")
    return HealthSettingsResponse.model_validate(config)
