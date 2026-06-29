"""
Seed Data — Self-Learning Config Presets & Memory Configs.

Populates the learning_configs table with realistic preset data for
every feature category so the UI and MCP agents have data to work with.

Usage:
    cd Backend Monorepo/Backend
    uv run python seed_learning_configs.py

This script is idempotent — re-running updates existing configs by name.
"""

from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from typing import Any

from common_lib.modules.data_storage.database.connection import get_session as _get_db_session
from common_lib.modules.knowledge_engine.services.instance_config_service import (
    CATEGORIES,
    InstanceConfigService,
)

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("seed.learning")

_svc = InstanceConfigService()


@contextmanager
def _get_session():
    """Get a sync DB session outside FastAPI."""
    gen = _get_db_session()
    session = next(gen)
    try:
        yield session
    finally:
        session.close()
        try:
            next(gen)
        except StopIteration:
            pass


# ── Seed Data ──────────────────────────────────────────────────────

SEED_CONFIGS: dict[str, list[dict[str, Any]]] = {
    "qualityLog": [
        {
            "name": "Standard Quality Log",
            "description": "Default quality logging config with moderate sampling",
            "config_data": {
                "enabled": True,
                "log_dir": "/var/log/quality/",
                "enabled_fields": ["precision", "recall", "latency_ms", "query", "result_count", "methods_used"],
                "sample_rate": 1.0,
                "max_entries": 10000,
                "retention_days": 30,
            },
        },
        {
            "name": "Minimal Logging",
            "description": "Low-overhead logging — only tracks failures and slow queries",
            "config_data": {
                "enabled": True,
                "log_dir": "/var/log/quality/minimal/",
                "enabled_fields": ["latency_ms", "error"],
                "sample_rate": 0.1,
                "max_entries": 5000,
                "retention_days": 7,
            },
        },
        {
            "name": "Debug Quality Log",
            "description": "Verbose quality logging for troubleshooting",
            "config_data": {
                "enabled": True,
                "log_dir": "/var/log/quality/debug/",
                "enabled_fields": ["precision", "recall", "latency_ms", "query", "result_count", "methods_used", "error", "user_rating"],
                "sample_rate": 1.0,
                "max_entries": 50000,
                "retention_days": 90,
            },
        },
    ],
    "autoEvolve": [
        {
            "name": "Balanced Evolution",
            "description": "Auto-evolve every 100 queries with moderate adaptation",
            "config_data": {
                "enabled": True,
                "interval": 100,
                "mutation_rate": 0.15,
                "crossover_rate": 0.7,
                "population_size": 20,
                "tournament_size": 3,
            },
        },
        {
            "name": "Conservative Evolution",
            "description": "Slow, careful evolution — only adapts after significant data",
            "config_data": {
                "enabled": True,
                "interval": 500,
                "mutation_rate": 0.05,
                "crossover_rate": 0.3,
                "population_size": 10,
                "tournament_size": 4,
            },
        },
        {
            "name": "Aggressive Evolution",
            "description": "Fast iteration — evolves frequently and explores aggressively",
            "config_data": {
                "enabled": True,
                "interval": 25,
                "mutation_rate": 0.3,
                "crossover_rate": 0.9,
                "population_size": 50,
                "tournament_size": 2,
            },
        },
    ],
    "scorer": [
        {
            "name": "Default Scoring",
            "description": "Standard scoring with balanced decay and minimum samples",
            "config_data": {
                "decay_rate": 0.1,
                "min_samples": 10,
                "recent_weight": 0.6,
                "historical_weight": 0.4,
                "normalize_scores": True,
            },
        },
        {
            "name": "Long Memory Scoring",
            "description": "Slow decay — weights historical performance more heavily",
            "config_data": {
                "decay_rate": 0.02,
                "min_samples": 5,
                "recent_weight": 0.3,
                "historical_weight": 0.7,
                "normalize_scores": True,
            },
        },
        {
            "name": "High Precision Scoring",
            "description": "Requires many samples before scoring, emphasizes precision",
            "config_data": {
                "decay_rate": 0.15,
                "min_samples": 25,
                "recent_weight": 0.8,
                "historical_weight": 0.2,
                "normalize_scores": True,
            },
        },
    ],
    "failure": [
        {
            "name": "Standard Failure Analysis",
            "description": "Default failure detection with moderate thresholds",
            "config_data": {
                "latency_threshold_ms": 5000.0,
                "min_severity": "warning",
                "enable_auto_heal": False,
                "max_failures_per_minute": 10,
                "notification_channel": "dashboard",
            },
        },
        {
            "name": "Strict Failure Detection",
            "description": "Low latency threshold, detects all issues immediately",
            "config_data": {
                "latency_threshold_ms": 1000.0,
                "min_severity": "info",
                "enable_auto_heal": True,
                "max_failures_per_minute": 3,
                "notification_channel": "slack",
            },
        },
        {
            "name": "Lenient Failure Mode",
            "description": "High tolerance — only flags critical failures",
            "config_data": {
                "latency_threshold_ms": 15000.0,
                "min_severity": "critical",
                "enable_auto_heal": False,
                "max_failures_per_minute": 50,
                "notification_channel": "email",
            },
        },
    ],
    "reasoner": [
        {
            "name": "Standard Meta Reasoner",
            "description": "Balanced meta-reasoning config for moderate query diversity",
            "config_data": {
                "short_query_threshold": 5,
                "enable_hyde_suggestion": True,
                "latency_weight": 0.3,
                "precision_weight": 0.5,
                "recall_weight": 0.2,
                "max_reasoning_depth": 3,
            },
        },
        {
            "name": "Precision-Focused Reasoning",
            "description": "Heavy precision weight, short queries trigger HYDE",
            "config_data": {
                "short_query_threshold": 10,
                "enable_hyde_suggestion": True,
                "latency_weight": 0.1,
                "precision_weight": 0.8,
                "recall_weight": 0.1,
                "max_reasoning_depth": 5,
            },
        },
    ],
    "belief": [
        {
            "name": "Standard Belief Revision",
            "description": "Moderate confidence threshold with moving average",
            "config_data": {
                "confidence_threshold": 0.6,
                "use_moving_average": True,
                "constant_learning_rate": 0.1,
                "max_beliefs": 1000,
                "decay_unused_after_days": 30,
            },
        },
        {
            "name": "Conservative Belief System",
            "description": "High confidence threshold — only keeps strong beliefs",
            "config_data": {
                "confidence_threshold": 0.85,
                "use_moving_average": True,
                "constant_learning_rate": 0.05,
                "max_beliefs": 500,
                "decay_unused_after_days": 60,
            },
        },
        {
            "name": "Adaptive Belief Revision",
            "description": "Fast learning rate, adapts quickly to new evidence",
            "config_data": {
                "confidence_threshold": 0.4,
                "use_moving_average": False,
                "constant_learning_rate": 0.3,
                "max_beliefs": 2000,
                "decay_unused_after_days": 7,
            },
        },
    ],
    "conflict": [
        {
            "name": "Default Conflict Resolution",
            "description": "Balanced strategy with moderate gaps for auto-resolution",
            "config_data": {
                "strategy": "majority_vote",
                "min_confidence_gap": 0.2,
                "min_source_trust_gap": 0.15,
                "enable_auto_resolution": True,
                "escalate_to_human": True,
            },
        },
        {
            "name": "Auto-Resolve All",
            "description": "Auto-resolves all conflicts using source trust weighting",
            "config_data": {
                "strategy": "source_trust_weighted",
                "min_confidence_gap": 0.05,
                "min_source_trust_gap": 0.05,
                "enable_auto_resolution": True,
                "escalate_to_human": False,
            },
        },
    ],
    "branching": [
        {
            "name": "Standard Evolution Branching",
            "description": "Moderate branching with balanced diversity",
            "config_data": {
                "enable_branching": True,
                "diversity_weight": 0.5,
                "max_branches": 5,
                "specialization_threshold": 0.7,
                "prune_stale_branches_after_days": 14,
            },
        },
        {
            "name": "Exploration Mode",
            "description": "Maximum diversity — explores many branches aggressively",
            "config_data": {
                "enable_branching": True,
                "diversity_weight": 0.9,
                "max_branches": 15,
                "specialization_threshold": 0.9,
                "prune_stale_branches_after_days": 7,
            },
        },
    ],
    "pruner": [
        {
            "name": "Standard Knowledge Pruning",
            "description": "Balanced pruning with moderate thresholds",
            "config_data": {
                "min_importance": 0.3,
                "max_age_hours": 720,
                "enable_user_review": True,
                "auto_prune_threshold": 0.7,
                "prune_batch_size": 100,
            },
        },
        {
            "name": "Aggressive Pruning",
            "description": "High auto-prune threshold, short retention",
            "config_data": {
                "min_importance": 0.5,
                "max_age_hours": 168,
                "enable_user_review": False,
                "auto_prune_threshold": 0.9,
                "prune_batch_size": 500,
            },
        },
        {
            "name": "Conservative Retention",
            "description": "Keeps most knowledge, long retention, manual review",
            "config_data": {
                "min_importance": 0.1,
                "max_age_hours": 4320,
                "enable_user_review": True,
                "auto_prune_threshold": 0.3,
                "prune_batch_size": 50,
            },
        },
    ],
}


# ── Executor ───────────────────────────────────────────────────────


async def seed_all() -> int:
    """Seed all configs. Returns total created/updated count."""
    total = 0

    with _get_session() as session:
        for category, configs in SEED_CONFIGS.items():
            for cfg in configs:
                try:
                    # Check if a config with this name already exists
                    existing = _svc.list_configs(
                        session, category=category, limit=500, offset=0
                    )
                    found = None
                    for ec in existing.get("configs", []):
                        if ec.get("name") == cfg["name"]:
                            found = ec
                            break

                    if found:
                        # Update existing config
                        _svc.update_category_config(
                            session,
                            config_id=found["id"],
                            config_data=cfg["config_data"],
                            name=cfg["name"],
                            description=cfg["description"],
                        )
                        logger.info(f"  Updated  '{cfg['name']}' ({category})")
                    else:
                        # Create new config
                        _svc.create_category_config(
                            session,
                            category=category,
                            config_data=cfg["config_data"],
                            name=cfg["name"],
                            description=cfg["description"],
                        )
                        logger.info(f"  Created  '{cfg['name']}' ({category})")

                    total += 1
                except Exception as e:
                    logger.warning(f"  Skipped  '{cfg['name']}' ({category}): {e}")

        session.commit()

    logger.info(f"\n✅ Seed complete: {total} configs processed")
    return total


async def main():
    logger.info("🌱 Seeding self-learning configuration presets...")
    logger.info(f"  Categories: {', '.join(c for c in CATEGORIES if c != 'full')}")
    await seed_all()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
