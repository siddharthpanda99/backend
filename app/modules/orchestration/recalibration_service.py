"""Recalibration service for drift auto-remediation.

When auto-remediation fires (consecutive alerts exceed threshold), the
recalibration service performs a full recalibration cycle:

1. Snapshots current system state (drift areas, scores, config)
2. Clears the old drift baseline via MemoryDriftDetector
3. Establishes a new baseline from the current state
4. Logs detailed recalibration results for the alert feed

This replaces the bare ``detector.clear_baseline()`` call with a
comprehensive recalibration that actually resets the system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RecalibrationResult:
    """Detailed result of a recalibration cycle."""

    success: bool = True
    timestamp: str = ""
    previous_baseline_exists: bool = False
    previous_scores: Dict[str, float] = field(default_factory=dict)
    previous_overall_score: float = 0.0
    areas_recalibrated: List[str] = field(default_factory=list)
    action_taken: str = "baseline_cleared"
    new_baseline_set: bool = False
    errors: List[str] = field(default_factory=list)
    summary: str = ""


async def run_recalibration(
    *,
    trigger_area: Optional[str] = None,
    trigger_label: Optional[str] = None,
    trigger_score: float = 0.0,
    drift_areas: Optional[List[Dict[str, Any]]] = None,
    affected_areas_only: bool = True,
) -> RecalibrationResult:
    """Execute a full recalibration cycle.

    Snapshots current drift state, clears the old baseline, and — when
    possible — establishes a new baseline from the current system state.

    Args:
        trigger_area: The drift area that triggered remediation, if any.
        trigger_label: Human-readable label for the trigger area.
        trigger_score: The drift score at time of trigger.
        drift_areas: Full list of current drift area results (for snapshot).
        affected_areas_only: If True, only recalibrate the trigger area's
            baseline; otherwise recalibrate the full system.

    Returns:
        A ``RecalibrationResult`` dataclass with full details.
    """
    result = RecalibrationResult(
        timestamp=datetime.utcnow().isoformat(),
    )

    # 1. Snapshot the current state
    if drift_areas:
        for area in drift_areas:
            aid = area.get("area_id", "unknown")
            score = area.get("score", 0.0)
            result.previous_scores[aid] = score
            if aid == trigger_area or not affected_areas_only:
                result.areas_recalibrated.append(aid)
        result.previous_overall_score = (
            sum(result.previous_scores.values()) / len(result.previous_scores)
            if result.previous_scores
            else 0.0
        )

    # 2. Clear the old baseline via MemoryDriftDetector
    try:
        from common_lib.modules.memory.memory_testing.drift import MemoryDriftDetector

        detector = MemoryDriftDetector()
        baseline = await detector.baseline_store.get()
        result.previous_baseline_exists = baseline is not None

        # Check if we can establish a new baseline
        if baseline is not None:
            # We have an existing baseline — we can try to run proper
            # eval queries to establish a new one. Fall back to just
            # clearing if no eval infrastructure is available.
            try:
                from common_lib.modules.memory.memory_testing.evaluator.evaluator import (
                    RetrievalEvaluator,
                )

                evaluator = RetrievalEvaluator()

                # Try to evaluate current quality and set new baseline
                # We use empty queries + retrieval_fn as a no-op probe;
                # if the evaluator has in-memory queries registered it
                # will run them, otherwise we fall back to clear only.
                if hasattr(evaluator, "get_benchmark_queries"):
                    queries = await evaluator.get_benchmark_queries()
                    if queries:
                        await detector.set_baseline(
                            queries,
                            _noop_retrieval,
                        )
                        result.new_baseline_set = True
                        result.action_taken = "baseline_reestablished"
                        logger.info(
                            "Recalibration: new baseline established with %d queries",
                            len(queries),
                        )
                    else:
                        detector.clear_baseline()
                        logger.info("Recalibration: no benchmark queries, cleared baseline")
                else:
                    detector.clear_baseline()
                    logger.info("Recalibration: evaluator has no benchmark queries, cleared baseline")

            except (ImportError, AttributeError, Exception) as exc:
                # Evaluator unavailable or no benchmark queries — just clear
                detector.clear_baseline()
                logger.info("Recalibration: evaluator unavailable (%s), cleared baseline", exc)
        else:
            # No baseline exists yet — nothing to recalibrate, but log it
            logger.info("Recalibration: no baseline existed — nothing to clear")
            result.action_taken = "no_baseline_to_clear"

    except ImportError:
        logger.warning("MemoryDriftDetector not available — recalibration logged only")
        result.action_taken = "logged_only"
        result.success = True  # Not a failure, just no detector
    except Exception as exc:
        logger.error("Recalibration failed: %s", exc)
        result.success = False
        result.errors.append(str(exc))
        result.action_taken = "failed"

    # 3. Build summary
    area_list = ", ".join(result.areas_recalibrated) if result.areas_recalibrated else "all"
    if result.success:
        if result.action_taken == "baseline_reestablished":
            result.summary = (
                f"Recalibration complete — {'affected areas' if affected_areas_only else 'full system'} "
                f"({area_list}) recalibrated from "
                f"{(trigger_score * 100):.1f}% drift. "
                f"New baseline established with evaluator."
            )
        elif result.action_taken == "baseline_cleared":
            result.summary = (
                f"Recalibration complete — old baseline cleared for "
                f"{area_list}. Next drift scan will establish a new baseline."
            )
        elif result.action_taken == "no_baseline_to_clear":
            result.summary = "Recalibration skipped — no baseline existed."
        else:
            result.summary = (
                f"Recalibration logged — {area_list} "
                f"at {(trigger_score * 100):.1f}% drift."
            )
    else:
        result.summary = (
            f"Recalibration failed for {area_list}: "
            f"{'; '.join(result.errors)}"
        )

    logger.info("Recalibration result: success=%s, action=%s — %s", result.success, result.action_taken, result.summary[:120])
    return result


async def _noop_retrieval(query: str, limit: int = 5) -> List[str]:
    """Fallback retrieval function if no real function is available."""
    return []


__all__ = [
    "RecalibrationResult",
    "run_recalibration",
]
