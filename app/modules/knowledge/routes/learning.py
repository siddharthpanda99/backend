"""Learning subsystem API routes — thin routers delegating to common_lib.

Endpoints: quality log, scorer, strategies, evolution, introspection,
meta-reasoner, failure analysis, beliefs, self-assessment, adaptive strategy,
heatmap, beliefs prune, auto-evolve config.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from sqlmodel import Session, select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.knowledge_engine.learning_factory import (
    get_learning_instance,
    get_orchestrator,
)
from common_lib.modules.knowledge_engine.models.db_records import (
    KnowledgeChunkRecord,
)
from common_lib.modules.knowledge_engine.services.analytics_service import (
    AnalyticsService,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Knowledge Learning"])


# Backward-compat alias used by learning_routes.py
def _get_learning_instance(name: str) -> Any:
    return get_learning_instance(name)


# ── Schemas ─────────────────────────────────────────────────


class ConfigUpdateRequest(BaseModel):
    updates: dict[str, Any] = Field(..., description="Config fields to update")


class QualityLogRecordRequest(BaseModel):
    query: str = Field(..., description="The retrieval query")
    result_count: int = Field(0, description="Number of results returned")
    latency_ms: float = Field(0.0, description="Retrieval latency")
    methods_used: list[str] = Field(default_factory=list)
    precision: Optional[float] = Field(None, ge=0.0, le=1.0)
    recall: Optional[float] = Field(None, ge=0.0, le=1.0)
    user_rating: Optional[float] = Field(None, ge=0.0, le=1.0)
    error: Optional[str] = Field(None)


class IntrospectionRequest(BaseModel):
    query: str = Field(..., description="The original retrieval query")
    result_count: int = Field(0, description="Number of results returned")
    latency_ms: float = Field(0.0)
    methods_used: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class MetaReasonerRequest(BaseModel):
    query: str = Field(..., description="The query to evaluate")
    plan: dict[str, Any] = Field(default_factory=dict)
    previous_outcomes: list[dict[str, Any]] = Field(default_factory=list)


class FailureAnalysisRequest(BaseModel):
    query: str = Field(..., description="The query that failed")
    error: str = Field(..., description="Error message")
    methods_used: list[str] = Field(default_factory=list)
    latency_ms: float = Field(0.0)


class SelfAssessRequest(BaseModel):
    run_full: bool = Field(True, description="Whether to run a full assessment")


# ── Quality Log ──────────────────────────────────────────────


@router.get("/learning/quality-log")
async def get_quality_log(
    n: int = Query(100, ge=1, le=1000, description="Number of recent entries"),
) -> dict[str, Any]:
    try:
        log = get_learning_instance("quality_log")
        recent = await log.get_recent(n=n)
        method_perf = await log.get_method_performance()
        failures = await log.get_failures()
        return {
            "success": True,
            "data": {
                "recent_outcomes": [o.model_dump() for o in recent],
                "total": len(recent),
                "method_performance": method_perf,
                "failure_count": len(failures),
            },
            "message": f"Quality log: {len(recent)} entries",
        }
    except Exception as e:
        logger.exception("Failed to get quality log")
        raise HTTPException(
            status_code=500, detail=f"Failed to get quality log: {str(e)}"
        )


@router.get("/learning/quality-log/config")
async def get_quality_log_config() -> dict[str, Any]:
    try:
        log = get_learning_instance("quality_log")
        config = log.get_config()
        return {
            "success": True,
            "data": config,
            "message": "Quality log configuration retrieved",
        }
    except Exception as e:
        logger.exception("Failed to get quality log config")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/learning/quality-log/config")
async def update_quality_log_config(request: ConfigUpdateRequest) -> dict[str, Any]:
    try:
        log = get_learning_instance("quality_log")
        enabled = request.updates.get("enabled")
        log_dir = request.updates.get("log_dir")
        enabled_fields = request.updates.get("enabled_fields")
        config = log.update_config(
            enabled=enabled if isinstance(enabled, bool) else None,
            log_dir=log_dir if isinstance(log_dir, str) else None,
            enabled_fields=enabled_fields if isinstance(enabled_fields, list) else None,
        )
        return {
            "success": True,
            "data": config,
            "message": "Quality log configuration updated",
        }
    except Exception as e:
        logger.exception("Failed to update quality log config")
        raise HTTPException(
            status_code=500, detail=f"Failed to update config: {str(e)}"
        )


@router.post("/learning/quality-log")
async def record_quality_log(request: QualityLogRecordRequest) -> dict[str, Any]:
    try:
        from common_lib.modules.knowledge_engine.learning.quality_log import (
            RetrievalOutcome,
        )

        log = get_learning_instance("quality_log")
        outcome = RetrievalOutcome(
            query=request.query,
            result_count=request.result_count,
            latency_ms=request.latency_ms,
            methods_used=request.methods_used,
            precision=request.precision,
            recall=request.recall,
            user_rating=request.user_rating,
            error=request.error,
        )
        await log.record(outcome)
        try:
            orchestrator = get_orchestrator()
            await orchestrator.orchestrate(
                methods_used=request.methods_used,
                user_rating=request.user_rating,
                latency_ms=request.latency_ms,
                query=request.query,
            )
        except Exception:
            logger.warning("Auto-evolution orchestration failed (non-blocking)")
        return {
            "success": True,
            "data": {"outcome_id": outcome.id},
            "message": "Outcome recorded",
        }
    except Exception as e:
        logger.exception("Failed to record quality log")
        raise HTTPException(status_code=500, detail=f"Failed to record: {str(e)}")


# ── Scorer + Strategies ──────────────────────────────────────


@router.get("/learning/scorer")
async def get_scorer_scores() -> dict[str, Any]:
    try:
        scorer = get_learning_instance("scorer")
        scores = await scorer.get_all_scores()
        ranking = await scorer.get_ranking()
        return {
            "success": True,
            "data": {"scores": scores, "ranking": ranking},
            "message": f"Scored {len(scores)} methods",
        }
    except Exception as e:
        logger.exception("Failed to get scorer scores")
        raise HTTPException(status_code=500, detail=f"Failed to get scores: {str(e)}")


@router.get("/learning/strategies")
async def get_strategies() -> dict[str, Any]:
    try:
        evolver = get_learning_instance("evolver")
        weights = await evolver.get_weights()
        generation = await evolver.get_generation()
        has_snapshot = await evolver.has_snapshot()
        return {
            "success": True,
            "data": {
                "weights": weights,
                "generation": generation,
                "default_weights": dict(evolver.DEFAULT_WEIGHTS),
                "has_snapshot": has_snapshot,
            },
            "message": f"Strategy generation {generation}",
        }
    except Exception as e:
        logger.exception("Failed to get strategies")
        raise HTTPException(
            status_code=500, detail=f"Failed to get strategies: {str(e)}"
        )


@router.post("/learning/evolve")
async def evolve_strategies() -> dict[str, Any]:
    try:
        scorer = get_learning_instance("scorer")
        evolver = get_learning_instance("evolver")
        method_scores = await scorer.get_all_scores()
        new_weights = await evolver.evolve(method_scores)
        generation = await evolver.get_generation()
        return {
            "success": True,
            "data": {
                "weights": new_weights,
                "generation": generation,
                "previous_scores": method_scores,
            },
            "message": f"Strategies evolved to generation {generation}",
        }
    except Exception as e:
        logger.exception("Failed to evolve strategies")
        raise HTTPException(status_code=500, detail=f"Failed to evolve: {str(e)}")


@router.get("/learning/evolve/auto-config")
async def get_auto_evolve_config() -> dict[str, Any]:
    try:
        evolver = get_learning_instance("evolver")
        config = await evolver.get_auto_config()
        return {
            "success": True,
            "data": config,
            "message": f"Auto-evolution {'enabled' if config['enabled'] else 'disabled'} every {config['interval']} queries",
        }
    except Exception as e:
        logger.exception("Failed to get auto-evolve config")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/learning/evolve/auto-config")
async def update_auto_evolve_config(request: ConfigUpdateRequest) -> dict[str, Any]:
    try:
        evolver = get_learning_instance("evolver")
        enabled = request.updates.get("enabled")
        interval = request.updates.get("interval")
        config = await evolver.set_auto_config(
            enabled=enabled if isinstance(enabled, bool) else None,
            interval=interval if isinstance(interval, int) else None,
        )
        return {
            "success": True,
            "data": config,
            "message": "Auto-evolution config updated",
        }
    except Exception as e:
        logger.exception("Failed to update auto-evolve config")
        raise HTTPException(
            status_code=500, detail=f"Failed to update config: {str(e)}"
        )


@router.post("/learning/evolve/rollback")
async def rollback_evolve_strategies() -> dict[str, Any]:
    try:
        evolver = get_learning_instance("evolver")
        has_snapshot = await evolver.has_snapshot()
        if not has_snapshot:
            raise HTTPException(
                status_code=400,
                detail="No snapshot available. Evolve strategies first before rolling back.",
            )
        restored_weights = await evolver.rollback()
        generation = await evolver.get_generation()
        return {
            "success": True,
            "data": {"weights": restored_weights, "generation": generation},
            "message": f"Strategies rolled back to generation {generation}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to rollback strategies")
        raise HTTPException(status_code=500, detail=f"Failed to rollback: {str(e)}")


# ── Introspection ────────────────────────────────────────────


@router.get("/learning/introspection")
async def run_introspection(
    query: str = Query(..., description="Original retrieval query"),
    result_count: int = Query(0, ge=0),
    latency_ms: float = Query(0.0, ge=0.0),
) -> dict[str, Any]:
    try:
        insp = get_learning_instance("introspection")
        report = await insp.inspect(
            query=query,
            result_count=result_count,
            latency_ms=latency_ms,
            methods_used=["dense", "sparse"],
        )
        return {
            "success": True,
            "data": report.model_dump(),
            "message": f"Retrieval quality: {report.overall_retrieval_quality:.2f}",
        }
    except Exception as e:
        logger.exception("Failed to run introspection")
        raise HTTPException(status_code=500, detail=f"Introspection failed: {str(e)}")


@router.post("/learning/meta-reasoner")
async def evaluate_plan(request: MetaReasonerRequest) -> dict[str, Any]:
    try:
        reasoner = get_learning_instance("meta_reasoner")
        result = await reasoner.evaluate_plan(
            query=request.query,
            plan=request.plan,
            previous_outcomes=request.previous_outcomes,
        )
        return {
            "success": True,
            "data": result,
            "message": f"Plan score: {result.get('plan_score', 0):.2f}",
        }
    except Exception as e:
        logger.exception("Failed to evaluate plan")
        raise HTTPException(status_code=500, detail=f"Plan evaluation failed: {str(e)}")


@router.post("/learning/failure-analysis")
async def analyze_failure(request: FailureAnalysisRequest) -> dict[str, Any]:
    try:
        analyzer = get_learning_instance("failure_analyzer")
        result = await analyzer.analyze(
            query=request.query,
            error=request.error,
            methods_used=request.methods_used,
            latency_ms=request.latency_ms,
        )
        stats = await analyzer.get_stats()
        return {
            "success": True,
            "data": {"analysis": result, "stats": stats},
            "message": f"Failure category: {result['category']}",
        }
    except Exception as e:
        logger.exception("Failed to analyze failure")
        raise HTTPException(
            status_code=500, detail=f"Failure analysis failed: {str(e)}"
        )


# ── Beliefs ──────────────────────────────────────────────────


@router.get("/learning/beliefs")
async def get_beliefs(threshold: float = Query(0.6, ge=0.0, le=1.0)) -> dict[str, Any]:
    try:
        reviser = get_learning_instance("belief_reviser")
        all_beliefs = await reviser.get_all_beliefs()
        recommendations = await reviser.recommend_methods(threshold=threshold)
        return {
            "success": True,
            "data": {
                "beliefs": all_beliefs,
                "recommendations": recommendations,
                "recommendation_threshold": threshold,
            },
            "message": f"{len(all_beliefs)} beliefs, {len(recommendations)} recommendations",
        }
    except Exception as e:
        logger.exception("Failed to get beliefs")
        raise HTTPException(status_code=500, detail=f"Failed to get beliefs: {str(e)}")


@router.post("/learning/beliefs/prune")
async def prune_beliefs(
    min_confidence: float = Query(0.3, ge=0.0, le=1.0),
) -> dict[str, Any]:
    try:
        reviser = get_learning_instance("belief_reviser")
        pruned = await reviser.prune_low_confidence(min_confidence=min_confidence)
        remaining = await reviser.get_all_beliefs()
        return {
            "success": True,
            "data": {"pruned": pruned, "remaining": len(remaining)},
            "message": f"Pruned {pruned} low-confidence beliefs",
        }
    except Exception as e:
        logger.exception("Failed to prune beliefs")
        raise HTTPException(
            status_code=500, detail=f"Failed to prune beliefs: {str(e)}"
        )


# ── Self-Assessment ──────────────────────────────────────────


@router.post("/learning/self-assess")
async def run_self_assessment(
    request: SelfAssessRequest | None = None,
) -> dict[str, Any]:
    try:
        finder = get_learning_instance("self_assessment")
        quality_log = get_learning_instance("quality_log")
        scorer = get_learning_instance("scorer")
        evolver = get_learning_instance("evolver")
        failure_analyzer = get_learning_instance("failure_analyzer")
        belief_reviser = get_learning_instance("belief_reviser")
        report = await finder.assess(
            quality_log=quality_log,
            scorer=scorer,
            evolver=evolver,
            failure_analyzer=failure_analyzer,
            belief_reviser=belief_reviser,
        )
        return {
            "success": True,
            "data": report.to_dict(),
            "message": f"Self-assessment complete: health={report.overall_health_score:.2f}, {len(report.findings)} findings, {len(report.recommendations)} recommendations",
        }
    except Exception as e:
        logger.exception("Self-assessment failed")
        raise HTTPException(status_code=500, detail=f"Self-assessment failed: {str(e)}")


@router.get("/learning/self-assess")
async def get_self_assessment(n: int = Query(1, ge=1, le=50)) -> dict[str, Any]:
    try:
        finder = get_learning_instance("self_assessment")
        reports = await finder.get_all_reports(n=n)
        total = await finder.get_report_count()
        return {
            "success": True,
            "data": {
                "reports": [r.to_dict() for r in reports],
                "total": total,
                "returned": len(reports),
            },
            "message": f"{len(reports)} report(s) retrieved",
        }
    except Exception as e:
        logger.exception("Failed to get self-assessment reports")
        raise HTTPException(status_code=500, detail=f"Failed to get reports: {str(e)}")


@router.get("/learning/self-assess/schedule")
async def get_self_assess_schedule() -> dict[str, Any]:
    try:
        finder = get_learning_instance("self_assessment")
        schedule = await finder.get_schedule()
        return {
            "success": True,
            "data": schedule,
            "message": "Schedule config retrieved",
        }
    except Exception as e:
        logger.exception("Failed to get schedule")
        raise HTTPException(status_code=500, detail=f"Failed to get schedule: {str(e)}")


@router.put("/learning/self-assess/schedule")
async def update_self_assess_schedule(request: ConfigUpdateRequest) -> dict[str, Any]:
    try:
        finder = get_learning_instance("self_assessment")
        enabled = request.updates.get("enabled")
        interval_minutes = request.updates.get("interval_minutes")
        schedule = await finder.set_schedule(
            enabled=enabled if isinstance(enabled, bool) else None,
            interval_minutes=interval_minutes
            if isinstance(interval_minutes, int)
            else None,
        )
        return {
            "success": True,
            "data": schedule,
            "message": f"Self-assessment scheduler {'enabled' if schedule['enabled'] else 'disabled'}",
        }
    except Exception as e:
        logger.exception("Failed to update schedule")
        raise HTTPException(
            status_code=500, detail=f"Failed to update schedule: {str(e)}"
        )


# ── Adaptive Strategy ────────────────────────────────────────


@router.get("/learning/adaptive-strategy")
async def get_adaptive_strategy_status() -> dict[str, Any]:
    try:
        adaptive = get_learning_instance("adaptive_strategy")
        status = adaptive.get_status()
        return {
            "success": True,
            "data": status,
            "message": f"Adaptive strategy: {status['selection_count']} selections, {len(status['feedback_entries'])} doc types tracked",
        }
    except Exception as e:
        logger.exception("Failed to get adaptive strategy status")
        raise HTTPException(
            status_code=500, detail=f"Failed to get adaptive strategy status: {str(e)}"
        )


@router.post("/learning/adaptive-strategy/learn")
async def trigger_adaptive_learning() -> dict[str, Any]:
    try:
        adaptive = get_learning_instance("adaptive_strategy")
        quality_log = get_learning_instance("quality_log")
        evolver = get_learning_instance("evolver")
        updated = await adaptive.learn_from_quality_log(quality_log)
        try:
            weights = await evolver.get_weights()
            if weights:
                adaptive.learn_from_evolver(weights)
        except Exception:
            pass
        return {
            "success": True,
            "data": {
                "feedback_records_updated": updated,
                "status": adaptive.get_status(),
            },
            "message": f"Adaptive strategy learned from {updated} quality log records",
        }
    except Exception as e:
        logger.exception("Failed to trigger adaptive learning")
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger adaptive learning: {str(e)}"
        )


# ── Heatmap ──────────────────────────────────────────────────


@router.get("/heatmap/query-scores")
async def get_heatmap_query_scores(
    n_queries: int = Query(50, ge=1, le=500),
    start_date: Optional[str] = Query(None, description="ISO date filter start"),
    end_date: Optional[str] = Query(None, description="ISO date filter end"),
    method: Optional[str] = Query(None, description="Filter by retrieval method"),
) -> dict[str, Any]:
    try:
        log = get_learning_instance("quality_log")
        recent = await log.get_recent(n=n_queries)
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date).replace(
                    tzinfo=timezone.utc
                )
                recent = [
                    o
                    for o in recent
                    if hasattr(o, "timestamp")
                    and o.timestamp
                    and o.timestamp >= start_dt
                ]
            except (ValueError, TypeError):
                pass
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date).replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )
                recent = [
                    o
                    for o in recent
                    if hasattr(o, "timestamp") and o.timestamp and o.timestamp <= end_dt
                ]
            except (ValueError, TypeError):
                pass
        if method and method.lower() != "all":
            method_lower = method.lower()
            recent = [
                o
                for o in recent
                if hasattr(o, "methods_used")
                and o.methods_used
                and any(m.lower() == method_lower for m in o.methods_used)
            ]
        bands = [
            {"label": "0.9-1.0", "min": 0.9, "count": 0},
            {"label": "0.75-0.9", "min": 0.75, "count": 0},
            {"label": "0.6-0.75", "min": 0.6, "count": 0},
            {"label": "0.4-0.6", "min": 0.4, "count": 0},
            {"label": "0.0-0.4", "min": 0.0, "count": 0},
        ]
        query_records = []
        scores = []
        for outcome in recent:
            score = None
            if hasattr(outcome, "precision") and outcome.precision is not None:
                score = outcome.precision
            elif hasattr(outcome, "user_rating") and outcome.user_rating is not None:
                score = outcome.user_rating
            if score is not None:
                scores.append(score)
                for b in bands:
                    if score >= b["min"]:
                        b["count"] += 1
                        break
                query_records.append(
                    {
                        "query": outcome.query[:80]
                        if hasattr(outcome, "query")
                        else "",
                        "score": score,
                        "result_count": outcome.result_count
                        if hasattr(outcome, "result_count")
                        else 0,
                        "latency_ms": outcome.latency_ms
                        if hasattr(outcome, "latency_ms")
                        else 0.0,
                        "methods_used": outcome.methods_used
                        if hasattr(outcome, "methods_used")
                        else [],
                        "error": outcome.error if hasattr(outcome, "error") else None,
                    }
                )
        avg_score = sum(scores) / len(scores) if scores else 0
        sorted_scores = sorted(scores)
        median_score = sorted_scores[len(sorted_scores) // 2] if sorted_scores else 0
        method_perf = (
            await log.get_method_performance()
            if hasattr(log, "get_method_performance")
            else {}
        )
        return {
            "success": True,
            "data": {
                "distribution": bands,
                "total_queries": len(scores),
                "avg_score": round(avg_score, 4),
                "median_score": round(median_score, 4),
                "high_count": sum(b["count"] for b in bands if b["min"] >= 0.75),
                "recent_queries": query_records[-20:],
                "method_performance": method_perf,
            },
            "message": f"Heatmap data for {len(scores)} queries",
        }
    except Exception as e:
        logger.exception("Failed to get heatmap query scores")
        raise HTTPException(
            status_code=500, detail=f"Failed to get heatmap data: {str(e)}"
        )


@router.get("/heatmap/document-stats")
async def get_heatmap_document_stats(
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        source_query_count: dict[str, int] = {}
        try:
            log = get_learning_instance("quality_log")
            recent = await log.get_recent(n=200)
            for outcome in recent:
                query_text = outcome.query if hasattr(outcome, "query") else ""
                for src_id in set(
                    session.exec(
                        select(KnowledgeChunkRecord.source_id).distinct()
                    ).all()
                ):
                    if src_id and src_id.lower() in query_text.lower():
                        source_query_count[src_id] = (
                            source_query_count.get(src_id, 0) + 1
                        )
        except Exception:
            pass
        data = AnalyticsService.document_stats(
            session=session, limit=limit, source_query_count=source_query_count or None
        )
        return {
            "success": True,
            "data": data,
            "message": f"Stats for {min(limit, len(data['documents']))} documents",
        }
    except Exception as e:
        logger.exception("Failed to get document stats")
        raise HTTPException(
            status_code=500, detail=f"Failed to get document stats: {str(e)}"
        )


__all__ = ["router"]
