"""Seed 20 real-world blueprint → composition scenarios into the database.

Each scenario:
1. Creates a BlueprintRecord with specific sections enabled
2. Deploys it → creates a CompositionRecord with resolved block IDs

Usage:
    uv run python scripts/seed_blueprint_scenarios.py
"""

import json
import logging
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.memory.blueprint_models import (
    BlueprintRecord,
    CompositionRecord,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Section IDs available in MemoryCreatorPage ───────────────────────────
# These map to block categories in the memory_driver via _SECTION_TO_CATEGORY.
ALL_SECTIONS = [
    "core",
    "context",
    "storage",
    "retrieval",
    "semantics",
    "security",
    "forecasting",
    "adaptation",
    "strategy",
    "execution",
    "economics",
    "causal",
    "testing",
    "federation",
    "versioning",
    "persona",
    "multimodal",
    "mql",
    "stores",
    "working",
    "observability",
]

# ── 20 Scenarios ─────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "id": "bp_personal_assistant",
        "name": "Personal AI Assistant",
        "description": "Everyday memory for a personal assistant: remembers user preferences, conversation history, and task context.",
        "sections": ["core", "context", "storage", "retrieval", "working"],
    },
    {
        "id": "bp_customer_support",
        "name": "Customer Support Bot",
        "description": "Support agent that remembers ticket history, customer identity, and product context with PII redaction.",
        "sections": ["core", "context", "retrieval", "security", "observability"],
    },
    {
        "id": "bp_healthcare",
        "name": "Healthcare Assistant (HIPAA)",
        "description": "HIPAA-compliant medical memory with full encryption, audit logging, and patient consent tracking.",
        "sections": ["core", "storage", "security", "versioning", "audit"],
    },
    {
        "id": "bp_code_review",
        "name": "Code Review Agent",
        "description": "Remembers codebase context, past reviews, coding standards, and diff history across branches.",
        "sections": ["core", "context", "semantics", "federation", "versioning"],
    },
    {
        "id": "bp_research_assistant",
        "name": "Research Paper Assistant",
        "description": "Indexes papers, extracts entities, builds citation graphs, and enables semantic search across your library.",
        "sections": ["core", "storage", "retrieval", "semantics", "mql"],
    },
    {
        "id": "bp_ecommerce_recs",
        "name": "E-Commerce Recommendation Engine",
        "description": "Tracks user browsing, purchase history, and preferences across sessions to power product recommendations.",
        "sections": ["core", "context", "storage", "forecasting", "economics"],
    },
    {
        "id": "bp_legal_docs",
        "name": "Legal Document Processor",
        "description": "GDPR-compliant document store with right-to-forget, ACL-based access, and full audit trail.",
        "sections": ["core", "storage", "security", "versioning", "causal"],
    },
    {
        "id": "bp_game_npc",
        "name": "Game NPC Memory System",
        "description": "Persistent NPC memory with forgetting curves, emotional state tracking, and story-event recall.",
        "sections": ["core", "context", "adaptation", "strategy", "persona"],
    },
    {
        "id": "bp_financial_advisor",
        "name": "Financial Advisor Agent",
        "description": "Tracks portfolio history, risk tolerance, market events, and generates economic forecasts.",
        "sections": ["core", "storage", "forecasting", "economics", "causal"],
    },
    {
        "id": "bp_education_tutor",
        "name": "Adaptive Education Tutor",
        "description": "Tracks student knowledge state, learning pace, misconceptions, and adapts lesson plans accordingly.",
        "sections": ["core", "context", "adaptation", "strategy", "testing"],
    },
    {
        "id": "bp_multi_agent",
        "name": "Multi-Agent Shared Memory",
        "description": "Shared memory pool for a team of agents — each agent reads/writes with federation and conflict resolution.",
        "sections": ["core", "storage", "federation", "versioning", "observability"],
    },
    {
        "id": "bp_devops_monitoring",
        "name": "DevOps Incident Monitor",
        "description": "Remembers incident history, runbook steps, alert patterns, and correlates events across services.",
        "sections": ["core", "context", "semantics", "observability", "causal"],
    },
    {
        "id": "bp_creative_writing",
        "name": "Creative Writing World Builder",
        "description": "Stores character profiles, locations, plot threads, and generates story-consistent text with multimodal mood boards.",
        "sections": ["core", "storage", "semantics", "multimodal", "persona"],
    },
    {
        "id": "bp_iot_dashboard",
        "name": "IoT Sensor Dashboard",
        "description": "Ingests sensor time-series, queries via MQL, detects anomalies, and stores historical readings.",
        "sections": ["core", "storage", "retrieval", "mql", "stores"],
    },
    {
        "id": "bp_language_learning",
        "name": "Language Learning Companion",
        "description": "Spaced-repetition vocabulary memory, grammar mistake tracking, and progress forecasting.",
        "sections": ["core", "context", "adaptation", "forecasting", "testing"],
    },
    {
        "id": "bp_social_media",
        "name": "Social Media Manager",
        "description": "Content calendar, audience engagement history, A/B test results, and versioned post drafts.",
        "sections": ["core", "storage", "strategy", "versioning", "testing"],
    },
    {
        "id": "bp_smart_home",
        "name": "Smart Home Controller",
        "description": "Learns occupant routines, adapts lighting/HVAC preferences, and stores device state history.",
        "sections": ["core", "context", "adaptation", "strategy", "execution"],
    },
    {
        "id": "bp_medical_research",
        "name": "Clinical Trial Analyzer",
        "description": "Stores trial data, patient outcomes, statistical correlations, and causal inference results.",
        "sections": ["core", "storage", "semantics", "causal", "mql"],
    },
    {
        "id": "bp_cybersecurity_siem",
        "name": "Cybersecurity SIEM",
        "description": "Threat intelligence feed, IOC memory, attack pattern matching, and security alert correlation.",
        "sections": ["core", "retrieval", "security", "observability", "testing"],
    },
    {
        "id": "bp_inventory",
        "name": "Inventory & Supply Chain",
        "description": "Product catalog, warehouse stock levels, supplier contracts, and demand forecasting.",
        "sections": ["core", "storage", "stores", "forecasting", "economics"],
    },
]


def build_section_config(section_ids: list[str]) -> dict:
    """Build a Creator-style sections dict with the given sections enabled."""
    config = {}
    for sid in section_ids:
        config[sid] = {
            "enabled": True,
            "label": sid.replace("_", " ").title(),
            "description": "",
            "icon": "🧠",
            "category": "general",
            "subsections": {},
        }
    return config


def resolve_blocks_for_sections(section_ids: list[str]) -> list[str]:
    """Resolve section IDs to block IDs using the same logic as deploy."""
    try:
        from common_lib.modules.memory.memory_driver import (
            CORE_BLOCKS,
            CONTEXT_BLOCKS,
            SEMANTIC_BLOCKS,
            SECURITY_BLOCKS,
            ADAPTATION_BLOCKS,
            STRATEGY_BLOCKS,
            EXECUTION_BLOCKS,
            FORECASTING_BLOCKS,
            ECONOMICS_BLOCKS,
            CAUSAL_BLOCKS,
            TESTING_BLOCKS,
            FEDERATION_BLOCKS,
            OBSERVABILITY_BLOCKS,
            VERSIONING_BLOCKS,
            PERSONA_BLOCKS,
            MULTIMODAL_BLOCKS,
            MQL_BLOCKS,
            STORES_BLOCKS,
            WORKING_BLOCKS,
        )

        all_blocks = (
            CORE_BLOCKS
            + CONTEXT_BLOCKS
            + SEMANTIC_BLOCKS
            + SECURITY_BLOCKS
            + ADAPTATION_BLOCKS
            + STRATEGY_BLOCKS
            + EXECUTION_BLOCKS
            + FORECASTING_BLOCKS
            + ECONOMICS_BLOCKS
            + CAUSAL_BLOCKS
            + TESTING_BLOCKS
            + FEDERATION_BLOCKS
            + OBSERVABILITY_BLOCKS
            + VERSIONING_BLOCKS
            + PERSONA_BLOCKS
            + MULTIMODAL_BLOCKS
            + MQL_BLOCKS
            + STORES_BLOCKS
            + WORKING_BLOCKS
        )
    except Exception as e:
        logger.warning(f"Cannot resolve blocks: {e}")
        return []

    category_map = {
        "core": "core",
        "context": "context",
        "storage": "storage",
        "retrieval": "retrieval",
        "semantics": "semantic",
        "security": "security",
        "forecasting": "forecasting",
        "adaptation": "adaptation",
        "strategy": "strategy",
        "execution": "execution",
        "economics": "economics",
        "causal": "causal",
        "testing": "testing",
        "federation": "federation",
        "observability": "observability",
        "versioning": "versioning",
        "persona": "persona",
        "multimodal": "multimodal",
        "mql": "mql",
        "stores": "stores",
        "working": "working",
        "audit": "observability",
    }

    block_ids = []
    for sid in section_ids:
        cat = category_map.get(sid)
        if not cat:
            continue
        for block in all_blocks:
            if block.category.value == cat:
                block_ids.append(block.id)
    return list(set(block_ids))


def seed():
    with next(get_session()) as session:
        existing_bps = session.exec(
            select(BlueprintRecord).where(BlueprintRecord.id.like("bp_%"))
        ).all()
        for bp in existing_bps:
            session.delete(bp)
        existing_comps = session.exec(
            select(CompositionRecord).where(
                CompositionRecord.source == "blueprint_seed"
            )
        ).all()
        for comp in existing_comps:
            session.delete(comp)
        session.commit()
        logger.info("Cleared previous seed data")

        now = datetime.now(timezone.utc).isoformat()
        total_blocks = 0

        for scenario in SCENARIOS:
            bp = BlueprintRecord(
                id=scenario["id"],
                name=scenario["name"],
                description=scenario["description"],
                entity_type="memory",
                sections=json.dumps(build_section_config(scenario["sections"])),
                created_at=now,
                updated_at=now,
            )
            session.add(bp)

            block_ids = resolve_blocks_for_sections(scenario["sections"])
            comp = CompositionRecord(
                id=f"comp_{scenario['id']}",
                name=f"Deployed: {scenario['name']}",
                description=f"Auto-deployed from {scenario['id']} — {scenario['description']}",
                block_ids=json.dumps(block_ids),
                source="blueprint_seed",
                blueprint_id=scenario["id"],
                created_at=now,
                updated_at=now,
            )
            session.add(comp)
            total_blocks += len(block_ids)

            logger.info(f"  ✅ {scenario['id']:40s} → {len(block_ids):2d} blocks")

        session.commit()

    print(
        f"\nSeeded {len(SCENARIOS)} blueprint scenarios ({total_blocks} total blocks)."
    )


if __name__ == "__main__":
    seed()
