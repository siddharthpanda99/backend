from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from app.modules.knowledge.routes import ConfigUpdateRequest, _get_learning_instance

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/learning/scorer/config")
async def get_scorer_config() -> dict[str, Any]:
    """Get the configuration for the Scorer."""
    try:
        scorer = _get_learning_instance("scorer")
        config = scorer.get_config()
        return {
            "success": True,
            "data": config,
            "message": "Scorer configuration retrieved",
        }
    except Exception as e:
        logger.exception("Failed to get scorer config")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/learning/scorer/config")
async def update_scorer_config(
    request: ConfigUpdateRequest,
) -> dict[str, Any]:
    """Update the configuration for the Scorer."""
    try:
        scorer = _get_learning_instance("scorer")
        decay_rate = request.updates.get("decay_rate")
        min_samples = request.updates.get("min_samples")
        
        config = scorer.update_config(
            decay_rate=float(decay_rate) if decay_rate is not None else None,
            min_samples=int(min_samples) if min_samples is not None else None,
        )
        return {
            "success": True,
            "data": config,
            "message": "Scorer configuration updated",
        }
    except Exception as e:
        logger.exception("Failed to update scorer config")
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@router.get("/learning/failure-analysis/config")
async def get_failure_config() -> dict[str, Any]:
    """Get the configuration for the Failure Analyzer."""
    try:
        analyzer = _get_learning_instance("failure_analyzer")
        config = analyzer.get_config()
        return {
            "success": True,
            "data": config,
            "message": "Failure analyzer configuration retrieved",
        }
    except Exception as e:
        logger.exception("Failed to get failure analyzer config")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/learning/failure-analysis/config")
async def update_failure_config(
    request: ConfigUpdateRequest,
) -> dict[str, Any]:
    """Update the configuration for the Failure Analyzer."""
    try:
        analyzer = _get_learning_instance("failure_analyzer")
        latency_threshold_ms = request.updates.get("latency_threshold_ms")
        min_severity = request.updates.get("min_severity")
        
        config = analyzer.update_config(
            latency_threshold_ms=float(latency_threshold_ms) if latency_threshold_ms is not None else None,
            min_severity=str(min_severity) if min_severity is not None else None,
        )
        return {
            "success": True,
            "data": config,
            "message": "Failure analyzer configuration updated",
        }
    except Exception as e:
        logger.exception("Failed to update failure analyzer config")
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@router.get("/learning/meta-reasoner/config")
async def get_reasoner_config() -> dict[str, Any]:
    """Get the configuration for the Meta Reasoner."""
    try:
        reasoner = _get_learning_instance("meta_reasoner")
        config = reasoner.get_config()
        return {
            "success": True,
            "data": config,
            "message": "Meta reasoner configuration retrieved",
        }
    except Exception as e:
        logger.exception("Failed to get meta reasoner config")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/learning/meta-reasoner/config")
async def update_reasoner_config(
    request: ConfigUpdateRequest,
) -> dict[str, Any]:
    """Update the configuration for the Meta Reasoner."""
    try:
        reasoner = _get_learning_instance("meta_reasoner")
        short_query_threshold = request.updates.get("short_query_threshold")
        enable_hyde_suggestion = request.updates.get("enable_hyde_suggestion")
        latency_weight = request.updates.get("latency_weight")
        
        config = reasoner.update_config(
            short_query_threshold=int(short_query_threshold) if short_query_threshold is not None else None,
            enable_hyde_suggestion=bool(enable_hyde_suggestion) if enable_hyde_suggestion is not None else None,
            latency_weight=float(latency_weight) if latency_weight is not None else None,
        )
        return {
            "success": True,
            "data": config,
            "message": "Meta reasoner configuration updated",
        }
    except Exception as e:
        logger.exception("Failed to update meta reasoner config")
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@router.get("/learning/beliefs/config")
async def get_belief_config() -> dict[str, Any]:
    """Get the configuration for the Belief Reviser."""
    try:
        reviser = _get_learning_instance("belief_reviser")
        config = reviser.get_config()
        return {
            "success": True,
            "data": config,
            "message": "Belief reviser configuration retrieved",
        }
    except Exception as e:
        logger.exception("Failed to get belief reviser config")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/learning/beliefs/config")
async def update_belief_config(
    request: ConfigUpdateRequest,
) -> dict[str, Any]:
    """Update the configuration for the Belief Reviser."""
    try:
        reviser = _get_learning_instance("belief_reviser")
        confidence_threshold = request.updates.get("confidence_threshold")
        use_moving_average = request.updates.get("use_moving_average")
        constant_learning_rate = request.updates.get("constant_learning_rate")
        
        config = reviser.update_config(
            confidence_threshold=float(confidence_threshold) if confidence_threshold is not None else None,
            use_moving_average=bool(use_moving_average) if use_moving_average is not None else None,
            constant_learning_rate=float(constant_learning_rate) if constant_learning_rate is not None else None,
        )
        return {
            "success": True,
            "data": config,
            "message": "Belief reviser configuration updated",
        }
    except Exception as e:
        logger.exception("Failed to update belief reviser config")
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@router.get("/learning/conflict-resolver/config")
async def get_conflict_resolver_config() -> dict[str, Any]:
    """Get the configuration for the Conflict Resolver."""
    try:
        resolver = _get_learning_instance("conflict_resolver")
        config = resolver.get_config()
        return {
            "success": True,
            "data": config,
            "message": "Conflict resolver configuration retrieved",
        }
    except Exception as e:
        logger.exception("Failed to get conflict resolver config")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/learning/conflict-resolver/config")
async def update_conflict_resolver_config(
    request: ConfigUpdateRequest,
) -> dict[str, Any]:
    """Update the configuration for the Conflict Resolver."""
    try:
        resolver = _get_learning_instance("conflict_resolver")
        strategy = request.updates.get("strategy")
        min_confidence_gap = request.updates.get("min_confidence_gap")
        min_source_trust_gap = request.updates.get("min_source_trust_gap")
        enable_auto_resolution = request.updates.get("enable_auto_resolution")
        
        config = resolver.update_config(
            strategy=str(strategy) if strategy is not None else None,
            min_confidence_gap=float(min_confidence_gap) if min_confidence_gap is not None else None,
            min_source_trust_gap=float(min_source_trust_gap) if min_source_trust_gap is not None else None,
            enable_auto_resolution=bool(enable_auto_resolution) if enable_auto_resolution is not None else None,
        )
        return {
            "success": True,
            "data": config,
            "message": "Conflict resolver configuration updated",
        }
    except Exception as e:
        logger.exception("Failed to update conflict resolver config")
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@router.get("/learning/evolution-branching/config")
async def get_evolution_branching_config() -> dict[str, Any]:
    """Get the configuration for the Evolution Branching system."""
    try:
        instance = _get_learning_instance("evolution_branching")
        config = instance.get_config()
        return {
            "success": True,
            "data": config,
            "message": "Evolution branching configuration retrieved",
        }
    except Exception as e:
        logger.exception("Failed to get evolution branching config")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/learning/evolution-branching/config")
async def update_evolution_branching_config(
    request: ConfigUpdateRequest,
) -> dict[str, Any]:
    """Update the configuration for the Evolution Branching system."""
    try:
        instance = _get_learning_instance("evolution_branching")
        enable_branching = request.updates.get("enable_branching")
        diversity_weight = request.updates.get("diversity_weight")
        max_branches = request.updates.get("max_branches")
        specialization_threshold = request.updates.get("specialization_threshold")
        
        config = instance.update_config(
            enable_branching=bool(enable_branching) if enable_branching is not None else None,
            diversity_weight=float(diversity_weight) if diversity_weight is not None else None,
            max_branches=int(max_branches) if max_branches is not None else None,
            specialization_threshold=float(specialization_threshold) if specialization_threshold is not None else None,
        )
        return {
            "success": True,
            "data": config,
            "message": "Evolution branching configuration updated",
        }
    except Exception as e:
        logger.exception("Failed to update evolution branching config")
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@router.get("/learning/knowledge-pruner/config")
async def get_knowledge_pruner_config() -> dict[str, Any]:
    """Get the configuration for the Knowledge Pruner."""
    try:
        instance = _get_learning_instance("knowledge_pruner")
        config = instance.get_config()
        return {
            "success": True,
            "data": config,
            "message": "Knowledge pruner configuration retrieved",
        }
    except Exception as e:
        logger.exception("Failed to get knowledge pruner config")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/learning/knowledge-pruner/config")
async def update_knowledge_pruner_config(
    request: ConfigUpdateRequest,
) -> dict[str, Any]:
    """Update the configuration for the Knowledge Pruner."""
    try:
        instance = _get_learning_instance("knowledge_pruner")
        min_importance = request.updates.get("min_importance")
        max_age_hours = request.updates.get("max_age_hours")
        enable_user_review = request.updates.get("enable_user_review")
        auto_prune_threshold = request.updates.get("auto_prune_threshold")
        
        config = instance.update_config(
            min_importance=float(min_importance) if min_importance is not None else None,
            max_age_hours=int(max_age_hours) if max_age_hours is not None else None,
            enable_user_review=bool(enable_user_review) if enable_user_review is not None else None,
            auto_prune_threshold=float(auto_prune_threshold) if auto_prune_threshold is not None else None,
        )
        return {
            "success": True,
            "data": config,
            "message": "Knowledge pruner configuration updated",
        }
    except Exception as e:
        logger.exception("Failed to update knowledge pruner config")
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")

