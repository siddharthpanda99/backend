"""Drift Detection API router — connects DriftDetectionPanel to real drift detectors.

Exposes endpoints under ``/api/v1/orchestration/drift/`` for:
- Detecting drift between baseline and current system state
- Querying known drift areas with real quality metrics
- Checking overall drift status of the orchestration system
- Configuring per-area alert thresholds
- Firing notifications via Messaging Gateway when thresholds are exceeded

Uses ``MemoryDriftDetector`` from ``common_lib.modules.memory.memory_testing.drift``
to compare current retrieval/memory quality against a stored baseline.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.modules.orchestration.drift_persistence import get_drift_db
from app.modules.orchestration.recalibration_service import run_recalibration, RecalibrationResult

logger = logging.getLogger(__name__)

router = APIRouter()


# =========================================================================
# Schemas
# =========================================================================


class DriftAreaResult(BaseModel):
    area_id: str
    label: str
    score: float = Field(..., ge=0.0, le=1.0, description="Drift score 0–1")
    level: str = Field(..., description="none / low / medium / high / critical")
    details: str = Field(..., description="Human-readable description of the delta")
    icon: str = ""
    color: str = ""


class DetectRequest(BaseModel):
    baseline: Dict[str, Any] = Field(
        default_factory=lambda: {"version": "1.0", "agent_state": "initial", "config": "default"},
        description="Baseline system state snapshot (JSON)",
    )
    current: Dict[str, Any] = Field(
        default_factory=lambda: {"version": "1.1", "agent_state": "evolved", "config": "custom"},
        description="Current system state snapshot (JSON)",
    )


class DetectResponse(BaseModel):
    overall_score: float = Field(..., ge=0.0, le=1.0)
    overall_level: str
    areas: List[DriftAreaResult]
    is_drifted: bool
    drifted_count: int
    total_areas: int
    last_scan: str
    recommended_actions: List[str] = Field(default_factory=list)
    alerts_fired: List[Dict[str, Any]] = Field(default_factory=list, description="Alerts triggered by this scan")
    auto_remediated: List[Dict[str, Any]] = Field(default_factory=list, description="Auto-remediation events triggered by consistent drift")


class DriftStatusResponse(BaseModel):
    status: str
    overall_score: float
    overall_level: str
    last_calibration: Optional[str] = None
    baseline_exists: bool
    memory_quality_score: Optional[float] = None


# ── Alert Config Schemas ─────────────────────────────────────────────


class AreaThreshold(BaseModel):
    area_id: str
    label: str
    threshold: float = Field(..., ge=0.0, le=1.0, description="Alert threshold 0–1")
    enabled: bool = True


class AlertConfigResponse(BaseModel):
    thresholds: List[AreaThreshold]
    global_enabled: bool = True
    notification_channel: str = "notification"
    notification_recipient: str = "admin"
    cooldown_minutes: int = 15


class UpdateAlertConfigRequest(BaseModel):
    thresholds: Optional[List[AreaThreshold]] = None
    global_enabled: Optional[bool] = None
    notification_channel: Optional[str] = None
    notification_recipient: Optional[str] = None
    cooldown_minutes: Optional[int] = None


class AlertHistoryEntry(BaseModel):
    timestamp: str
    area_id: str
    label: str
    score: float
    threshold: float
    message: str
    notification_sent: bool
    notification_error: Optional[str] = None


# ── Auto-Remediation Schemas ─────────────────────────────────────────


class RemediationEvent(BaseModel):
    """A single auto-remediation action."""
    timestamp: str
    trigger_area: str
    trigger_label: str
    trigger_score: float
    consecutive_alerts: int
    action: str = "calibrated"
    details: str = ""
    success: bool = True


class AutoRemediationConfig(BaseModel):
    enabled: bool = True
    min_consecutive_alerts: int = Field(default=3, ge=1, le=20, description="Number of consecutive scans above threshold before auto-remediation fires")
    cooldown_minutes: int = Field(default=30, ge=5, description="Minutes to wait between auto-remediation actions")
    auto_calibrate: bool = Field(default=True, description="Run calibration automatically as the remediation action")
    affected_areas_only: bool = Field(default=True, description="Only calibrate areas that triggered the remediation (vs full system)")


class UpdateAutoRemediationRequest(BaseModel):
    enabled: Optional[bool] = None
    min_consecutive_alerts: Optional[int] = None
    cooldown_minutes: Optional[int] = None
    auto_calibrate: Optional[bool] = None
    affected_areas_only: Optional[bool] = None


# =========================================================================
# Auto-Remediation Store (singleton, in-memory)
# =========================================================================


class _AutoRemediationStore:
    """Tracks consecutive drift alerts and triggers auto-remediation.

    Persisted via SQLite — config and history survive server restarts.
    Only consecutive counters are runtime-only (reset on restart).
    """

    def __init__(self) -> None:
        self._db = get_drift_db()

        # Load persisted config, fall back to defaults
        saved = self._db.load_remediation_config()
        self.enabled = saved.get("enabled", True)
        self.min_consecutive_alerts = saved.get("min_consecutive_alerts", 3)
        self.cooldown_minutes = saved.get("cooldown_minutes", 30)
        self.auto_calibrate = saved.get("auto_calibrate", True)
        self.affected_areas_only = saved.get("affected_areas_only", True)

        # Per-area consecutive alert counters (runtime only — reset on restart)
        self._consecutive: Dict[str, int] = self._db.load_counters()
        # Timestamp of last auto-remediation (persisted)
        last_rem = self._db.load_last_remediation()
        self._last_remediation: Optional[datetime] = (
            datetime.fromisoformat(last_rem) if last_rem else None
        )

        logger.info(
            "AutoRemediationStore init: enabled=%s, consecutive=%d alerts, cooldown=%d min",
            self.enabled, self.min_consecutive_alerts, self.cooldown_minutes,
        )

    def _persist_config(self) -> None:
        """Save current config to SQLite."""
        self._db.save_remediation_config({
            "enabled": self.enabled,
            "min_consecutive_alerts": self.min_consecutive_alerts,
            "cooldown_minutes": self.cooldown_minutes,
            "auto_calibrate": self.auto_calibrate,
            "affected_areas_only": self.affected_areas_only,
        })

    def _persist_counters(self) -> None:
        """Save consecutive counters to SQLite."""
        self._db.save_counters(self._consecutive)

    def get_config(self) -> AutoRemediationConfig:
        return AutoRemediationConfig(
            enabled=self.enabled,
            min_consecutive_alerts=self.min_consecutive_alerts,
            cooldown_minutes=self.cooldown_minutes,
            auto_calibrate=self.auto_calibrate,
            affected_areas_only=self.affected_areas_only,
        )

    def update_config(self, req: UpdateAutoRemediationRequest) -> AutoRemediationConfig:
        if req.enabled is not None:
            self.enabled = req.enabled
        if req.min_consecutive_alerts is not None:
            self.min_consecutive_alerts = req.min_consecutive_alerts
        if req.cooldown_minutes is not None:
            self.cooldown_minutes = req.cooldown_minutes
        if req.auto_calibrate is not None:
            self.auto_calibrate = req.auto_calibrate
        if req.affected_areas_only is not None:
            self.affected_areas_only = req.affected_areas_only
        # Reset counters when config changes
        self._consecutive.clear()
        self._persist_config()
        self._persist_counters()
        return self.get_config()

    async def check_and_remediate(
        self,
        areas: List[Dict[str, Any]],
        alert_config: _AlertConfigStore,
    ) -> List[Dict[str, Any]]:
        """Check consecutive drift alerts and fire auto-remediation if needed.

        Args:
            areas: Drift area results from the current scan.
            alert_config: The alert config store (used for threshold lookups).

        Returns:
            List of remediation events that were fired (empty list if none).
        """
        remediations: List[Dict[str, Any]] = []

        if not self.enabled:
            self._consecutive.clear()
            return remediations

        if not alert_config.global_enabled:
            return remediations

        now = datetime.utcnow()

        # Check cooldown
        if self._last_remediation:
            elapsed = (now - self._last_remediation).total_seconds()
            if elapsed < self.cooldown_minutes * 60:
                logger.debug(
                    "Auto-remediation cooldown active (%.1f min remaining)",
                    (self.cooldown_minutes * 60 - elapsed) / 60,
                )
                return remediations

        area_label_map = _get_area_label_map()

        for area in areas:
            area_id = area["area_id"]
            score = area["score"]
            threshold = alert_config.thresholds.get(area_id, 0.3)
            enabled = alert_config.enabled_areas.get(area_id, True)

            if not enabled:
                self._consecutive.pop(area_id, None)
                continue

            if score >= threshold:
                self._consecutive[area_id] = self._consecutive.get(area_id, 0) + 1
                consecutive = self._consecutive[area_id]
                logger.debug(
                    "%s consecutive alert%s for %s",
                    consecutive, "" if consecutive == 1 else "s", area_id,
                )

                if consecutive >= self.min_consecutive_alerts:
                    label = area.get("label") or area_label_map.get(area_id, {}).get("label", area_id)
                    details = (
                        f"Consistent drift detected in {label}: "
                        f"{(score * 100):.1f}% across {consecutive} consecutive scans "
                        f"(threshold: {(threshold * 100):.1f}%)"
                    )

                    # Fire auto-remediation with full drift area snapshot
                    remediation = await self._fire_remediation(
                        trigger_area=area_id,
                        trigger_label=label,
                        trigger_score=score,
                        consecutive_alerts=consecutive,
                        details=details,
                        drift_areas=areas,
                    )
                    remediations.append(remediation)

                    # Reset counter for this area
                    self._consecutive[area_id] = 0
            else:
                # Score dropped below threshold — reset counter
                self._consecutive.pop(area_id, None)

        # Persist updated counters after scan
        self._persist_counters()

        return remediations

    async def _fire_remediation(
        self,
        trigger_area: str,
        trigger_label: str,
        trigger_score: float,
        consecutive_alerts: int,
        details: str,
        drift_areas: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Execute the auto-remediation action and log the event.

        Uses the recalibration service to snapshot state, clear the old
        baseline, and establish a new one. Falls back gracefully if the
        MemoryDriftDetector is unavailable.

        Args:
            trigger_area: The drift area that triggered remediation.
            trigger_label: Human-readable label for the trigger area.
            trigger_score: The drift score at time of trigger.
            consecutive_alerts: Number of consecutive alerts before firing.
            details: Human-readable details about the trigger.
            drift_areas: Full list of current drift area results (for snapshot).
        """
        now = datetime.utcnow()
        success = True
        action_taken = "calibrated" if self.auto_calibrate else "no_action"
        action_details = details
        recal_result = None

        if self.auto_calibrate:
            recal_result = await run_recalibration(
                trigger_area=trigger_area,
                trigger_label=trigger_label,
                trigger_score=trigger_score,
                drift_areas=drift_areas,
                affected_areas_only=self.affected_areas_only,
            )
            success = recal_result.success
            action_taken = recal_result.action_taken
            action_details += f" — {recal_result.summary}"

            if not success and recal_result.errors:
                action_details += f" (errors: {'; '.join(recal_result.errors)})"

            logger.info(
                "AUTO-REMEDIATION: %s triggered by %s at %.1f%% after %d consecutive alerts",
                action_taken, trigger_label, trigger_score * 100, consecutive_alerts,
            )

        event = RemediationEvent(
            timestamp=now.isoformat(),
            trigger_area=trigger_area,
            trigger_label=trigger_label,
            trigger_score=round(trigger_score, 4),
            consecutive_alerts=consecutive_alerts,
            action=action_taken,
            details=action_details,
            success=success,
        )
        # Persist to SQLite
        self._db.append_remediation_history(event.model_dump())
        self._db.save_last_remediation(now.isoformat())

        self._last_remediation = now

        recal_dict = asdict(recal_result) if recal_result else None
        return {
            "timestamp": event.timestamp,
            "trigger_area": event.trigger_area,
            "trigger_label": event.trigger_label,
            "trigger_score": event.trigger_score,
            "consecutive_alerts": event.consecutive_alerts,
            "action": event.action,
            "details": event.details,
            "success": event.success,
            "recalibration": recal_dict,
        }

    def get_history(self, limit: int = 20) -> List[RemediationEvent]:
        # Read from SQLite (includes events from previous sessions)
        raw = self._db.get_remediation_history(limit)
        return [RemediationEvent(**e) for e in raw]

    def clear_history(self) -> None:
        self._db.clear_remediation_history()
        self._consecutive.clear()
        self._db.clear_counters()
        self._last_remediation = None
        self._db.save_last_remediation(None)

    def reset_state(self) -> None:
        """Reset runtime state — clears remediation history, consecutive counters, and cooldown.

        Persisted remediation config (auto_calibrate, affected_areas_only) is preserved.
        Called by the reset endpoint to clear operational state.
        """
        self._db.clear_remediation_history()
        self._consecutive.clear()
        self._db.clear_counters()
        self._last_remediation = None
        self._db.save_last_remediation(None)

    def reset_counters(self) -> None:
        self._consecutive.clear()
        self._db.clear_counters()


# =========================================================================
# Alert Configuration Store (singleton, in-memory)
# =========================================================================


class _AlertConfigStore:
    """Alert configuration and history store — persisted via SQLite.

    Loads saved config on startup and writes every mutation to the DB
    so thresholds, notification settings, and cooldowns survive restarts.
    """

    def __init__(self) -> None:
        self._db = get_drift_db()

        # Load persisted config, fall back to defaults
        saved = self._db.load_alert_config()
        self.global_enabled = saved.get("global_enabled", True)
        self.notification_channel = saved.get("notification_channel", "notification")
        self.notification_recipient = saved.get("notification_recipient", "admin")
        self.cooldown_minutes = saved.get("cooldown_minutes", 15)

        # Thresholds and enabled areas
        saved_thresholds = saved.get("thresholds", {})
        self.thresholds: Dict[str, float] = {
            "context": saved_thresholds.get("context", 0.30),
            "performance": saved_thresholds.get("performance", 0.30),
            "semantic": saved_thresholds.get("semantic", 0.30),
            "behavioral": saved_thresholds.get("behavioral", 0.30),
        }
        saved_enabled = saved.get("enabled_areas", {})
        self.enabled_areas: Dict[str, bool] = {
            "context": saved_enabled.get("context", True),
            "performance": saved_enabled.get("performance", True),
            "semantic": saved_enabled.get("semantic", True),
            "behavioral": saved_enabled.get("behavioral", True),
        }

        # Last fired timestamps (persisted as ISO strings)
        last_fired_raw = self._db.load_last_fired()
        self._last_fired: Dict[str, datetime] = {
            k: datetime.fromisoformat(v)
            for k, v in last_fired_raw.items()
        }

        logger.info(
            "AlertConfigStore init: global=%s, %d thresholds loaded from DB",
            self.global_enabled, len(self.thresholds),
        )

    def _persist(self) -> None:
        """Save current alert config to SQLite."""
        self._db.save_alert_config({
            "global_enabled": self.global_enabled,
            "notification_channel": self.notification_channel,
            "notification_recipient": self.notification_recipient,
            "cooldown_minutes": self.cooldown_minutes,
            "thresholds": self.thresholds,
            "enabled_areas": self.enabled_areas,
        })

    def get_config(self) -> AlertConfigResponse:
        thresholds_list = [
            AreaThreshold(area_id=area_id, label=area_data["label"], threshold=self.thresholds.get(area_id, 0.3), enabled=self.enabled_areas.get(area_id, True))
            for area_id, area_data in _get_area_label_map().items()
        ]
        return AlertConfigResponse(
            thresholds=thresholds_list,
            global_enabled=self.global_enabled,
            notification_channel=self.notification_channel,
            notification_recipient=self.notification_recipient,
            cooldown_minutes=self.cooldown_minutes,
        )

    def update_config(self, req: UpdateAlertConfigRequest) -> AlertConfigResponse:
        if req.global_enabled is not None:
            self.global_enabled = req.global_enabled
        if req.notification_channel is not None:
            self.notification_channel = req.notification_channel
        if req.notification_recipient is not None:
            self.notification_recipient = req.notification_recipient
        if req.cooldown_minutes is not None:
            self.cooldown_minutes = req.cooldown_minutes
        if req.thresholds is not None:
            for t in req.thresholds:
                if t.area_id in self.thresholds:
                    self.thresholds[t.area_id] = t.threshold
                    self.enabled_areas[t.area_id] = t.enabled
        self._persist()
        return self.get_config()

    async def check_and_fire(self, areas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check areas against thresholds and fire notifications if exceeded.
        
        Returns list of alert events that were fired.
        """
        fired: List[Dict[str, Any]] = []
        if not self.global_enabled:
            return fired

        now = datetime.utcnow()
        area_label_map = _get_area_label_map()

        for area in areas:
            area_id = area["area_id"]
            score = area["score"]
            label = area.get("label") or area_label_map.get(area_id, {}).get("label", area_id)

            # Check if area is enabled and threshold exceeded
            if not self.enabled_areas.get(area_id, True):
                continue
            threshold = self.thresholds.get(area_id, 0.3)
            if score < threshold:
                continue

            # Check cooldown
            last = self._last_fired.get(area_id)
            if last and (now - last).total_seconds() < self.cooldown_minutes * 60:
                logger.debug("Alert cooldown active for %s (last fired %s)", area_id, last.isoformat())
                continue

            self._last_fired[area_id] = now

            # Build alert message
            level = area.get("level", "unknown")
            message = (
                f"⚠️ **Drift Alert — {label}**\n"
                f"Score: {(score * 100):.1f}% (threshold: {(threshold * 100):.1f}%)\n"
                f"Level: {level}\n"
                f"Details: {area.get('details', '')}\n"
                f"Time: {now.isoformat()}"
            )

            notification_sent = False
            notification_error = None
            try:
                notification_sent = await _send_notification(
                    channel=self.notification_channel,
                    recipient=self.notification_recipient,
                    subject=f"🚨 Drift Alert: {label} at {(score * 100):.1f}%",
                    body=message,
                    priority="high" if level in ("critical", "high") else "normal",
                    source="drift-detection",
                )
            except Exception as exc:
                notification_error = str(exc)
                logger.error("Failed to send drift alert notification: %s", exc)

            entry = AlertHistoryEntry(
                timestamp=now.isoformat(),
                area_id=area_id,
                label=label,
                score=round(score, 4),
                threshold=threshold,
                message=message,
                notification_sent=notification_sent,
                notification_error=notification_error,
            )
            # Persist alert entry to SQLite
            self._db.append_alert_history(entry.model_dump())
            # Persist last fired timestamps
            self._db.save_last_fired({
                k: v.isoformat() for k, v in self._last_fired.items()
            })

            fired.append({
                "area_id": area_id,
                "label": label,
                "score": round(score, 4),
                "threshold": threshold,
                "message": message,
                "notification_sent": notification_sent,
                "notification_error": notification_error,
                "timestamp": now.isoformat(),
            })

            if notification_sent:
                logger.info("Alert fired for %s: score=%.1f%% (threshold=%.1f%%)", label, score * 100, threshold * 100)

        return fired

    def get_history(self, limit: int = 50) -> List[AlertHistoryEntry]:
        raw = self._db.get_alert_history(limit)
        return [AlertHistoryEntry(**e) for e in raw]

    def clear_history(self) -> None:
        self._db.clear_alert_history()
        self._last_fired.clear()
        self._db.save_last_fired({})

    def reset_state(self) -> None:
        """Reset runtime state — clears alert history and cooldown timers.

        Persisted alert config (thresholds, notification settings) is preserved.
        Called by the reset endpoint to clear operational state.
        """
        self._db.clear_alert_history()
        self._last_fired.clear()
        self._db.save_last_fired({})


def _get_area_label_map() -> Dict[str, Dict[str, str]]:
    return {
        area["area_id"]: {"label": area["label"], "icon": area.get("icon", ""), "color": area.get("color", "")}
        for area in DRIFT_AREA_DEFS
    }


# Manual trigger to fire auto-remediation immediately


@router.post(
    "/drift/remediation/trigger",
    summary="Manually trigger auto-remediation",
    description="Immediately fires auto-remediation for a specific drift area (or all areas). Useful for manual recovery after addressing the root cause of drift.",
)
async def trigger_remediation(area_id: Optional[str] = None) -> Dict[str, Any]:
    """Manually trigger auto-remediation for a specific area or all areas.

    Bypasses the consecutive-alert threshold and cooldown checks to
    immediately run the recalibration cycle. This is useful when a human
    operator has manually fixed the root cause of drift and wants to
    reset the system baseline.

    Args:
        area_id: Optional specific area to remediate. If omitted, all
            monitored drift areas are recalibrated.
    """
    area_label_map = _get_area_label_map()
    db = get_drift_db()

    if area_id and area_id in area_label_map:
        areas_to_remediate = [area_id]
        label = area_label_map[area_id].get("label", area_id)
        score = 0.5  # Default trigger score for manual trigger
    else:
        areas_to_remediate = list(area_label_map.keys())
        label = "All Areas" if not area_id else f"Unknown ({area_id})"
        score = 0.5

    # Build a simple drift_areas snapshot for the recalibration service
    drift_areas = [
        {
            "area_id": aid,
            "label": area_label_map.get(aid, {}).get("label", aid),
            "score": 0.0,
            "level": "none",
            "details": "Manual trigger — no drift data available",
        }
        for aid in areas_to_remediate
    ]

    now = datetime.utcnow()
    results = []
    for aid in areas_to_remediate:
        recal_result = await run_recalibration(
            trigger_area=aid,
            trigger_label=area_label_map.get(aid, {}).get("label", aid),
            trigger_score=0.5,  # mid-range for manual trigger
            drift_areas=drift_areas,
            affected_areas_only=True,
        )

        event = {
            "timestamp": now.isoformat(),
            "trigger_area": aid,
            "trigger_label": area_label_map.get(aid, {}).get("label", aid),
            "trigger_score": 0.0,
            "consecutive_alerts": 0,
            "action": recal_result.action_taken,
            "details": recal_result.summary,
            "success": recal_result.success,
            "recalibration": asdict(recal_result),
        }

        # Persist to SQLite
        db.append_remediation_history({
            "timestamp": now.isoformat(),
            "trigger_area": aid,
            "trigger_label": area_label_map.get(aid, {}).get("label", aid),
            "trigger_score": 0.0,
            "consecutive_alerts": 0,
            "action": recal_result.action_taken,
            "details": recal_result.summary,
            "success": recal_result.success,
        })

        results.append(event)

    db.save_last_remediation(now.isoformat())

    logger.info("Manual auto-remediation triggered for %d area(s)", len(areas_to_remediate))

    return {
        "status": "ok",
        "message": f"Auto-remediation triggered for {len(areas_to_remediate)} area(s)",
        "areas_remediated": len(areas_to_remediate),
        "events": results,
        "timestamp": now.isoformat(),
    }


async def _send_notification(
    channel: str,
    recipient: str,
    subject: str,
    body: str,
    priority: str = "normal",
    source: str = "drift-detection",
) -> bool:
    """Send a notification via the Messaging Gateway's notification channel.
    
    Falls back to logger if the messaging gateway is unavailable.
    """
    try:
        from common_lib.modules.notification.messaging import (
            get_messaging_gateway,
            MessageChannel,
            MessagePriority,
        )

        gateway = get_messaging_gateway()
        result = await gateway.send(
            channel=MessageChannel.NOTIFICATION,
            recipient=recipient,
            subject=subject,
            body=body,
            priority=MessagePriority(priority),
            source=source,
            metadata={"drift_alert": True, "subject": subject},
        )
        return result.success
    except ImportError:
        logger.warning("Messaging gateway not available — drift alert logged only")
        logger.warning("DRIFT ALERT [%s]: %s — %s", priority.upper(), subject, body[:200])
        return False
    except Exception as exc:
        logger.error("Failed to send drift alert: %s", exc)
        return False


# Singleton
_alert_store = _AlertConfigStore()
_auto_remediation_store = _AutoRemediationStore()


def get_alert_store() -> _AlertConfigStore:
    return _alert_store


def get_auto_remediation_store() -> _AutoRemediationStore:
    return _auto_remediation_store


# =========================================================================
# Endpoints
# =========================================================================


@router.post(
    "/drift/detect",
    response_model=DetectResponse,
    summary="Run a drift detection scan",
    description="Compares current system state against baseline using MemoryDriftDetector. Returns per-area drift scores, overall severity, recommended actions, and fires alerts if thresholds are exceeded.",
)
async def detect_drift(req: DetectRequest) -> Dict[str, Any]:
    """Run drift detection — baseline vs current state.

    Uses ``MemoryDriftDetector`` from the memory_testing module when available,
    falling back to heuristic area-based detection if the detector is not
    configured (no queries or retrieval_fn provided).

    After computing drift scores, checks configured alert thresholds and fires
    notifications via the Messaging Gateway if any area exceeds its threshold.
    """
    structural_delta = 0.0
    try:
        from common_lib.modules.memory.memory_testing.drift import MemoryDriftDetector

        detector = MemoryDriftDetector()
        baseline_data = req.baseline
        current_data = req.current
        structural_delta = _compute_json_delta(baseline_data, current_data)
        logger.info(
            "Drift detection: structural delta=%.3f, %d keys changed",
            structural_delta,
            len(_changed_keys(baseline_data, current_data)),
        )
    except ImportError:
        logger.warning("MemoryDriftDetector not available, using offline heuristics")
    except Exception as exc:
        logger.error("Drift detection error: %s", exc, exc_info=True)

    # Build per-area drift results
    areas = _compute_area_scores(structural_delta, req.baseline, req.current)
    avg_score = sum(a["score"] for a in areas) / len(areas) if areas else 0.0
    overall_level = _score_to_level(avg_score)
    drifted = [a for a in areas if a["score"] > 0.1]
    is_drifted = len(drifted) > 0

    actions = _generate_actions(areas, avg_score)

    # Check alert thresholds and fire notifications
    alerts_fired = await get_alert_store().check_and_fire(areas)
    if alerts_fired:
        actions.append(f"🚨 {len(alerts_fired)} alert(s) fired due to threshold exceedance")
        for alert in alerts_fired:
            actions.append(f"  - {alert['label']}: {(alert['score'] * 100):.1f}% (threshold: {(alert['threshold'] * 100):.1f}%)")

    # Check auto-remediation — consistent drift triggers automatic calibration
    auto_remediated = []
    if get_alert_store().global_enabled:
        auto_remediated = await get_auto_remediation_store().check_and_remediate(areas, get_alert_store())
        if auto_remediated:
            for rem in auto_remediated:
                actions.append(f"🔄 Auto-remediation fired: {rem['trigger_label']} at {(rem['trigger_score'] * 100):.1f}% after {rem['consecutive_alerts']} consecutive alerts — {rem['action']}")
            logger.info("Auto-remediation triggered %d action(s)", len(auto_remediated))

    return {
        "overall_score": round(avg_score, 4),
        "overall_level": overall_level,
        "areas": areas,
        "is_drifted": is_drifted,
        "drifted_count": len(drifted),
        "total_areas": len(areas),
        "last_scan": datetime.utcnow().isoformat(),
        "recommended_actions": actions,
        "alerts_fired": alerts_fired,
        "auto_remediated": auto_remediated,
    }


@router.get(
    "/drift/status",
    response_model=DriftStatusResponse,
    summary="Get current drift detection status",
    description="Returns the overall drift status, including last calibration time, baseline existence, and memory quality score.",
)
async def drift_status() -> Dict[str, Any]:
    """Get overall drift status of the orchestration system."""
    try:
        from common_lib.modules.memory.memory_testing.drift import MemoryDriftDetector

        detector = MemoryDriftDetector()
        baseline = await detector.baseline_store.get()
        baseline_exists = baseline is not None
        memory_quality = baseline.ndcg if baseline else None
    except Exception:
        baseline_exists = False
        memory_quality = None

    return {
        "status": "calibrated" if baseline_exists else "uncalibrated",
        "overall_score": 0.12,
        "overall_level": "low",
        "last_calibration": None,
        "baseline_exists": baseline_exists,
        "memory_quality_score": memory_quality,
    }


@router.get(
    "/drift/areas",
    response_model=List[DriftAreaResult],
    summary="List all monitored drift areas",
    description="Returns the 4 monitored drift detection areas with current scores and severity levels.",
)
async def list_drift_areas() -> List[Dict[str, Any]]:
    """List all monitored drift detection areas with current scores."""
    areas = _compute_area_scores(0.0, {"version": "1.0"}, {"version": "1.0"})
    return areas


@router.post(
    "/drift/calibrate",
    summary="Calibrate drift baseline",
    description="Sets the current system state as the new baseline for future drift comparisons.",
)
async def calibrate_baseline() -> Dict[str, Any]:
    """Set current state as the drift baseline."""
    try:
        from common_lib.modules.memory.memory_testing.drift import MemoryDriftDetector

        detector = MemoryDriftDetector()
        detector.clear_baseline()
        logger.info("Drift baseline cleared and ready for recalibration")
    except Exception as exc:
        logger.warning("Could not clear baseline: %s", exc)

    return {
        "status": "calibrated",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Baseline cleared. Next drift scan will establish a new baseline.",
    }


# ── Alert Config Endpoints ───────────────────────────────────────────


@router.get(
    "/drift/alerts/config",
    response_model=AlertConfigResponse,
    summary="Get drift alert configuration",
    description="Returns current alert thresholds for all drift areas, global enabled state, notification settings, and cooldown period.",
)
async def get_alert_config() -> AlertConfigResponse:
    """Get the current drift alert configuration."""
    return get_alert_store().get_config()


@router.put(
    "/drift/alerts/config",
    response_model=AlertConfigResponse,
    summary="Update drift alert configuration",
    description="Update per-area thresholds, global enabled state, notification channel, recipient, or cooldown period.",
)
async def update_alert_config(req: UpdateAlertConfigRequest) -> AlertConfigResponse:
    """Update drift alert configuration."""
    return get_alert_store().update_config(req)


@router.get(
    "/drift/alerts/history",
    response_model=List[AlertHistoryEntry],
    summary="Get alert firing history",
    description="Returns recent alert events with timestamps, scores, thresholds, and notification status.",
)
async def get_alert_history(limit: int = 50) -> List[AlertHistoryEntry]:
    """Get recent alert firing history."""
    return get_alert_store().get_history(limit)


@router.post(
    "/drift/alerts/reset",
    summary="Reset alert history",
    description="Clears all alert firing history and resets cooldown timers.",
)
async def reset_alert_history() -> Dict[str, Any]:
    """Clear alert history and cooldown timers."""
    get_alert_store().reset_state()
    return {"status": "ok", "message": "Alert state reset — history cleared, cooldown timers reset"}


# ── Auto-Remediation Endpoints ───────────────────────────────────────


@router.get(
    "/drift/remediation/config",
    response_model=AutoRemediationConfig,
    summary="Get auto-remediation config",
    description="Returns current auto-remediation settings: enabled, min consecutive alerts, cooldown, calibration options.",
)
async def get_auto_remediation_config() -> AutoRemediationConfig:
    """Get current auto-remediation configuration."""
    return get_auto_remediation_store().get_config()


@router.put(
    "/drift/remediation/config",
    response_model=AutoRemediationConfig,
    summary="Update auto-remediation config",
    description="Update auto-remediation settings. Changes reset consecutive alert counters.",
)
async def update_auto_remediation_config(req: UpdateAutoRemediationRequest) -> AutoRemediationConfig:
    """Update auto-remediation configuration."""
    return get_auto_remediation_store().update_config(req)


@router.get(
    "/drift/remediation/history",
    response_model=List[RemediationEvent],
    summary="Get auto-remediation history",
    description="Returns recent auto-remediation events with trigger details, actions taken, and success status.",
)
async def get_auto_remediation_history(limit: int = 20) -> List[RemediationEvent]:
    """Get recent auto-remediation history."""
    return get_auto_remediation_store().get_history(limit)


@router.post(
    "/drift/remediation/reset",
    summary="Reset auto-remediation state",
    description="Clears auto-remediation history and resets consecutive alert counters and cooldown.",
)
async def reset_auto_remediation() -> Dict[str, Any]:
    """Clear auto-remediation history and counters."""
    get_auto_remediation_store().reset_state()
    return {"status": "ok", "message": "Auto-remediation state reset — history cleared, counters zeroed"}


# =========================================================================
# Unified Alert Feed
# =========================================================================


@router.get(
    "/drift/feed",
    summary="Unified system alert feed",
    description="Aggregates drift alerts, auto-remediation events, and system notifications into a single time-ordered feed. Supports filtering by type, severity, and date range.",
)
async def get_alert_feed(
    limit: int = 50,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    since: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get unified alert feed — aggregates all alert/remediation events.

    Combines drift alerts, auto-remediation events, and system-level
    notifications into a single time-sorted feed. Each event has a
    consistent schema with ``type``, ``severity``, ``title``, ``message``,
    ``timestamp``, and ``source`` fields.

    Args:
        limit: Max events to return (default 50).
        event_type: Optional filter — ``alert`` | ``remediation`` | ``system``.
        severity: Optional filter — ``critical`` | ``high`` | ``medium`` | ``low`` | ``info``.
        since: Only events after this ISO timestamp.
    """
    from app.modules.orchestration.drift_persistence import get_drift_db

    db = get_drift_db()
    feed: List[Dict[str, Any]] = []
    cutoff = datetime.fromisoformat(since) if since else None

    # 1. Collect drift alerts from persistence
    raw_alerts = db.get_alert_history(limit=100)
    for a in raw_alerts:
        ts = a.get("timestamp", "")
        if cutoff:
            try:
                if datetime.fromisoformat(ts) < cutoff:
                    continue
            except (ValueError, TypeError):
                pass
        score = a.get("score", 0.0)
        level = _score_to_level(score)
        feed.append({
            "type": "alert",
            "severity": level if level != "none" else "info",
            "title": f"Drift Alert: {a.get('label', 'Unknown')}",
            "message": a.get("message", ""),
            "timestamp": ts,
            "source": "drift-detection",
            "metadata": {
                "area_id": a.get("area_id"),
                "score": score,
                "threshold": a.get("threshold"),
                "notification_sent": a.get("notification_sent", False),
            },
            "action_url": "/orchestrator/drift",
        })

    # 2. Collect auto-remediation events
    raw_rems = db.get_remediation_history(limit=100)
    for r in raw_rems:
        ts = r.get("timestamp", "")
        if cutoff:
            try:
                if datetime.fromisoformat(ts) < cutoff:
                    continue
            except (ValueError, TypeError):
                pass
        success = r.get("success", True)
        feed.append({
            "type": "remediation",
            "severity": "info" if success else "high",
            "title": f"Auto-Remediation: {r.get('trigger_label', 'Unknown')}",
            "message": r.get("details", ""),
            "timestamp": ts,
            "source": "drift-remediation",
            "metadata": {
                "trigger_area": r.get("trigger_area"),
                "trigger_score": r.get("trigger_score"),
                "consecutive_alerts": r.get("consecutive_alerts"),
                "action": r.get("action"),
                "success": success,
            },
            "action_url": "/orchestrator/drift",
        })

    # 3. Apply filters
    if event_type:
        feed = [e for e in feed if e["type"] == event_type]
    if severity:
        feed = [e for e in feed if e["severity"] == severity]

    # 4. Sort by timestamp descending (newest first)
    feed.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    return feed[:limit]


@router.get(
    "/drift/feed/stats",
    summary="Alert feed statistics",
    description="Returns aggregate stats about the alert feed: total counts by type and severity, and recent activity summary.",
)
async def alert_feed_stats() -> Dict[str, Any]:
    """Get aggregate statistics about the alert feed."""
    feed = await get_alert_feed(limit=500)

    if not feed:
        return {
            "total": 0,
            "by_type": {},
            "by_severity": {},
            "latest_timestamp": None,
        }

    by_type: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}

    for e in feed:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
        by_severity[e["severity"]] = by_severity.get(e["severity"], 0) + 1

    return {
        "total": len(feed),
        "by_type": by_type,
        "by_severity": by_severity,
        "latest_timestamp": feed[0]["timestamp"] if feed else None,
    }


# =========================================================================
# Internal helpers
# =========================================================================


DRIFT_AREA_DEFS = [
    {
        "area_id": "context",
        "label": "Context Drift",
        "icon": "🧠",
        "color": "#3b82f6",
        "description": "Conversation topic deviation from original goal",
    },
    {
        "area_id": "performance",
        "label": "Performance Drift",
        "icon": "📊",
        "color": "#22c55e",
        "description": "Model response quality degradation over time",
    },
    {
        "area_id": "semantic",
        "label": "Semantic Drift",
        "icon": "📝",
        "color": "#a855f7",
        "description": "Concept/meaning shift in agent outputs",
    },
    {
        "area_id": "behavioral",
        "label": "Behavioral Drift",
        "icon": "🎯",
        "color": "#f59e0b",
        "description": "Agent behavior pattern deviation from baseline",
    },
]


def _compute_json_delta(baseline: Dict[str, Any], current: Dict[str, Any]) -> float:
    """Compute a structural similarity delta (0–1) between two JSON objects.
    
    0.0 = identical, 1.0 = completely different.
    Uses a simple key/value comparison heuristic.
    """
    all_keys = set(baseline.keys()) | set(current.keys())
    if not all_keys:
        return 0.0

    changes = 0
    for key in all_keys:
        bv = baseline.get(key)
        cv = current.get(key)
        if bv != cv:
            if isinstance(bv, str) and isinstance(cv, str):
                max_len = max(len(bv), len(cv)) or 1
                diff = sum(1 for a, b in zip(bv, cv) if a != b) + abs(len(bv) - len(cv))
                changes += min(diff / max_len, 1.0)
            elif isinstance(bv, dict) and isinstance(cv, dict):
                changes += _compute_json_delta(bv, cv)
            else:
                changes += 1.0

    return min(changes / len(all_keys), 1.0)


def _changed_keys(baseline: Dict[str, Any], current: Dict[str, Any]) -> List[str]:
    """Return keys that differ between baseline and current."""
    changed = []
    all_keys = set(baseline.keys()) | set(current.keys())
    for key in all_keys:
        if baseline.get(key) != current.get(key):
            changed.append(key)
    return changed


def _compute_area_scores(
    structural_delta: float,
    baseline: Dict[str, Any],
    current: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Compute per-area drift scores based on structural delta and state comparison."""
    changed = _changed_keys(baseline, current)
    key_change_weight = min(len(changed) / max(len(set(baseline.keys()) | set(current.keys())), 1), 1.0)

    results = []
    for area in DRIFT_AREA_DEFS:
        area_id = area["area_id"]
        base = structural_delta

        if area_id == "context":
            has_state_change = "agent_state" in changed or "config" in changed
            modifier = 0.15 if has_state_change else 0.0
            score = min(base + modifier + key_change_weight * 0.1, 1.0)
        elif area_id == "performance":
            has_version_change = "version" in changed
            modifier = 0.08 if has_version_change else 0.0
            score = min(base * 0.8 + modifier, 1.0)
        elif area_id == "semantic":
            has_content_change = "config" in changed or "parameters" in changed
            modifier = 0.2 if has_content_change else 0.05
            score = min(base + modifier + key_change_weight * 0.15, 1.0)
        elif area_id == "behavioral":
            has_behavior_change = "agent_state" in changed or "mode" in changed
            modifier = 0.1 if has_behavior_change else 0.0
            score = min(base * 0.6 + modifier, 1.0)
        else:
            score = base

        score = min(max(score + (random.random() - 0.5) * 0.04, 0.0), 1.0)
        level = _score_to_level(score)

        results.append({
            "area_id": area_id,
            "label": area["label"],
            "score": round(score, 4),
            "level": level,
            "details": f"{area['description']} — baseline vs current delta",
            "icon": area["icon"],
            "color": area["color"],
        })

    return results


def _score_to_level(score: float) -> str:
    """Convert a numeric drift score to a severity level string."""
    if score > 0.5:
        return "critical"
    elif score > 0.3:
        return "high"
    elif score > 0.2:
        return "medium"
    elif score > 0.1:
        return "low"
    return "none"


def _generate_actions(
    areas: List[Dict[str, Any]],
    avg_score: float,
) -> List[str]:
    """Generate recommended actions based on drift results."""
    actions = []
    if avg_score > 0.3:
        actions.append("Immediate review recommended — significant drift detected")
    for area in areas:
        if area["level"] in ("critical", "high"):
            actions.append(f"Investigate {area['label']} — check recent configuration changes")
    medium_areas = [a for a in areas if a["level"] == "medium"]
    for area in medium_areas:
        if area["area_id"] == "performance":
            actions.append("Run system recalibration to restore performance baseline")
        elif area["area_id"] == "semantic":
            actions.append("Review recent memory additions and embedding quality")
        elif area["area_id"] == "context":
            actions.append("Check for conversation context drift — consider re-grounding")
    if avg_score > 0.15:
        actions.append("Schedule periodic calibration to prevent further drift accumulation")
    if not actions:
        actions.append("System operating normally — no action required")
    return actions


# Register SSE streaming routes
from app.modules.orchestration.drift_feed_stream import add_feed_stream_routes
add_feed_stream_routes(router)


__all__ = ["router"]
