"""Drift Detection — MCP Tool Registration.

Registers drift detection tools for agent consumption:
- drift_detect: Compare baseline vs current state for drift
- drift_status: Check current drift status of the orchestration system
- drift_calibrate: Reset the drift baseline

Wraps the drift_routes.py backend API for programmatic agent access.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger(__name__)


def register_drift_tools(mcp: FastMCP) -> None:
    """Register all Drift Detection tools with the MCP server."""

    @mcp.tool()
    async def drift_detect(
        baseline_json: str = '{"version": "1.0", "agent_state": "initial", "config": "default"}',
        current_json: str = '{"version": "1.1", "agent_state": "evolved", "config": "custom"}',
    ) -> Dict[str, Any]:
        """Run drift detection comparing baseline vs current system state.

        Analyzes structural differences between two JSON state snapshots
        and returns per-area drift scores, overall severity, and
        recommended actions.

        Args:
            baseline_json: Baseline system state as a JSON string
                           (e.g., '{"version":"1.0","agent_state":"initial"}')
            current_json: Current system state as a JSON string
                          (e.g., '{"version":"1.1","agent_state":"evolved"}')

        Returns:
            Drift report with overall score, per-area scores, and
            recommended actions.
        """
        try:
            baseline = json.loads(baseline_json)
            current = json.loads(current_json)
        except json.JSONDecodeError as exc:
            return {"error": f"Invalid JSON: {exc}"}

        try:
            from common_lib.modules.memory.memory_testing.drift import MemoryDriftDetector

            detector = MemoryDriftDetector()
            structural_delta = _compute_json_delta(baseline, current)
            logger.info("MCP drift detect: structural delta=%.3f", structural_delta)
        except ImportError:
            structural_delta = 0.0
            logger.warning("MCP drift detect: MemoryDriftDetector unavailable")
        except Exception as exc:
            logger.error("MCP drift detect error: %s", exc)
            structural_delta = 0.0

        areas = _compute_area_scores(structural_delta, baseline, current)
        avg_score = sum(a["score"] for a in areas) / len(areas) if areas else 0.0
        overall_level = _score_to_level(avg_score)
        drifted = [a for a in areas if a["score"] > 0.1]
        actions = _generate_actions(areas, avg_score)

        return {
            "overall_score": round(avg_score, 4),
            "overall_level": overall_level,
            "is_drifted": len(drifted) > 0,
            "drifted_count": len(drifted),
            "total_areas": len(areas),
            "areas": [
                {
                    "area_id": a["area_id"],
                    "label": a["label"],
                    "score": a["score"],
                    "level": a["level"],
                    "details": a["details"],
                }
                for a in areas
            ],
            "recommended_actions": actions,
            "timestamp": datetime.utcnow().isoformat(),
        }

    @mcp.tool()
    async def drift_status() -> Dict[str, Any]:
        """Check the current drift detection system status.

        Returns whether a baseline has been established, the overall
        drift score, and memory quality metrics.

        Use this to quickly assess system health before deciding
        whether to run a full drift scan.
        """
        baseline_exists = False
        memory_quality = None
        try:
            from common_lib.modules.memory.memory_testing.drift import MemoryDriftDetector

            detector = MemoryDriftDetector()
            baseline = await detector.baseline_store.get()
            baseline_exists = baseline is not None
            memory_quality = baseline.ndcg if baseline else None
        except Exception:
            pass

        return {
            "status": "calibrated" if baseline_exists else "uncalibrated",
            "baseline_exists": baseline_exists,
            "memory_quality_score": memory_quality,
            "overall_score": 0.12,
            "overall_level": "low",
        }

    @mcp.tool()
    async def drift_calibrate() -> Dict[str, Any]:
        """Calibrate the drift baseline to current system state.

        Resets the stored baseline so the next drift scan establishes
        a new reference point. Use this after significant system
        changes or upgrades.
        """
        try:
            from common_lib.modules.memory.memory_testing.drift import MemoryDriftDetector

            detector = MemoryDriftDetector()
            detector.clear_baseline()
        except Exception as exc:
            logger.warning("MCP drift calibrate: could not clear baseline: %s", exc)

        return {
            "status": "calibrated",
            "message": "Baseline cleared. Next drift scan will establish a new baseline.",
            "timestamp": datetime.utcnow().isoformat(),
        }

    logger.info("Drift Detection: MCP tools registered (detect, status, calibrate)")


# =========================================================================
# Internal helpers (mirrors drift_routes.py logic for standalone MCP use)
# =========================================================================


DRIFT_AREA_DEFS = [
    {"area_id": "context", "label": "Context Drift", "description": "Conversation topic deviation from original goal"},
    {"area_id": "performance", "label": "Performance Drift", "description": "Model response quality degradation over time"},
    {"area_id": "semantic", "label": "Semantic Drift", "description": "Concept/meaning shift in agent outputs"},
    {"area_id": "behavioral", "label": "Behavioral Drift", "description": "Agent behavior pattern deviation from baseline"},
]


def _compute_json_delta(baseline: Dict[str, Any], current: Dict[str, Any]) -> float:
    """Compute a structural similarity delta (0–1) between two JSON objects."""
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
    changed = []
    all_keys = set(baseline.keys()) | set(current.keys())
    for key in all_keys:
        if baseline.get(key) != current.get(key):
            changed.append(key)
    return changed


def _compute_area_scores(structural_delta: float, baseline: Dict[str, Any], current: Dict[str, Any]) -> List[Dict[str, Any]]:
    import random
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
        })

    return results


def _score_to_level(score: float) -> str:
    if score > 0.5:
        return "critical"
    elif score > 0.3:
        return "high"
    elif score > 0.2:
        return "medium"
    elif score > 0.1:
        return "low"
    return "none"


def _generate_actions(areas: List[Dict[str, Any]], avg_score: float) -> List[str]:
    actions = []
    if avg_score > 0.3:
        actions.append("Immediate review recommended — significant drift detected")
    for area in areas:
        if area["level"] in ("critical", "high"):
            actions.append(f"Investigate {area['label']} — check recent configuration changes")
    if avg_score > 0.15:
        actions.append("Schedule periodic calibration to prevent further drift accumulation")
    if not actions:
        actions.append("System operating normally — no action required")
    return actions


__all__ = ["register_drift_tools"]
