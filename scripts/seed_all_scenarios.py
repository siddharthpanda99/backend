"""Seed 40 real-world blueprint -> composition scenarios into the database.

Each scenario:
1. Creates a BlueprintRecord with specific sections enabled and configured
2. Deploys it -> creates a CompositionRecord with resolved block IDs

Usage:
    uv run python scripts/seed_all_scenarios.py
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

# Force block registry to populate
from common_lib.modules.memory.memory_driver import ensure_registry_initialized

ensure_registry_initialized()

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
    ALL_BLOCKS,
)

# Build a canonical section -> block ID mapping
SECTION_BLOCK_MAP = {
    "core": [b.id for b in CORE_BLOCKS],
    "context": [b.id for b in CONTEXT_BLOCKS],
    "storage": [
        b.id
        for b in CORE_BLOCKS
        if "store" in b.id or "tier" in b.id or "cache" in b.id
    ],
    "retrieval": [
        b.id
        for b in ALL_BLOCKS
        if "retriev" in b.id
        or "search" in b.id
        or "vector" in b.id
        or "rerank" in b.id
        or "hybrid" in b.id
    ],
    "semantics": [b.id for b in SEMANTIC_BLOCKS],
    "security": [b.id for b in SECURITY_BLOCKS],
    "forecasting": [b.id for b in FORECASTING_BLOCKS],
    "adaptation": [b.id for b in ADAPTATION_BLOCKS],
    "strategy": [b.id for b in STRATEGY_BLOCKS],
    "execution": [b.id for b in EXECUTION_BLOCKS],
    "economics": [b.id for b in ECONOMICS_BLOCKS],
    "causal": [b.id for b in CAUSAL_BLOCKS],
    "testing": [b.id for b in TESTING_BLOCKS],
    "federation": [b.id for b in FEDERATION_BLOCKS],
    "observability": [b.id for b in OBSERVABILITY_BLOCKS],
    "versioning": [b.id for b in VERSIONING_BLOCKS],
    "persona": [b.id for b in PERSONA_BLOCKS],
    "multimodal": [b.id for b in MULTIMODAL_BLOCKS],
    "mql": [b.id for b in MQL_BLOCKS],
    "stores": [b.id for b in STORES_BLOCKS],
    "working": [b.id for b in WORKING_BLOCKS],
    "audit": [b.id for b in OBSERVABILITY_BLOCKS],
}

# ── 40 Scenarios (10 Simple, 10 Medium, 10 Complex, 10 Comprehensive) ─────

SCENARIOS = [
    # ── Simple (1-2 sections enabled) ──
    {
        "id": "bp_simple_dial_buffer",
        "name": "Dialogue Buffer Memory",
        "description": "Basic dialogue buffer memory system. Maintains a rolling log of recent user-assistant interactions.",
        "sections": ["core", "working"],
        "overrides": {"core.crud_ops": {"auto_store": True}, "working.chain_of_thought": {"max_steps": 3}},
    },
    {
        "id": "bp_simple_sess_state",
        "name": "Session State Tracker",
        "description": "Lightweight context tracker to maintain active user session variables and short-term conversation state.",
        "sections": ["context"],
        "overrides": {"context.context_build": {"max_tokens": 2048, "strategy": "recent_first"}},
    },
    {
        "id": "bp_simple_embed_cache",
        "name": "Local Embedding Cache",
        "description": "Basic caching configuration for local embeddings to avoid redundant network calls and optimize latency.",
        "sections": ["storage"],
        "overrides": {"storage.cache_config": {"enabled": True, "max_entries": 500, "eviction_policy": "lru"}},
    },
    {
        "id": "bp_simple_focus_buf",
        "name": "Focus Attention Buffer",
        "description": "Applies simple recency and attention decay curves to retain focus on current task parameters.",
        "sections": ["working", "context"],
        "overrides": {"context.attention": {"enabled": True, "decay_rate": 0.15}},
    },
    {
        "id": "bp_simple_user_prof",
        "name": "Basic User Profile Memory",
        "description": "Stores static user preferences and attributes in a simple relational SQL adapter.",
        "sections": ["core"],
        "overrides": {"core.storage_config": {"adapter": "relational"}},
    },
    {
        "id": "bp_simple_rerank",
        "name": "Simple Reranker",
        "description": "Basic text-matching and search reranking for quick lookup of factual knowledge.",
        "sections": ["retrieval"],
        "overrides": {"retrieval.text_search": {"enabled": True, "default_top_k": 5}},
    },
    {
        "id": "bp_simple_system_log",
        "name": "System Log Buffer",
        "description": "Keeps a rolling buffer of system warnings and operations log for debugging and error diagnosis.",
        "sections": ["observability"],
        "overrides": {"observability.health": {"enabled": True, "interval_seconds": 60}},
    },
    {
        "id": "bp_simple_scratchpad",
        "name": "Single-Agent Scratchpad",
        "description": "Temporary scratchpad memory for intermediate agent execution steps and calculations.",
        "sections": ["working"],
        "overrides": {"working.chain_of_thought": {"max_steps": 5}},
    },
    {
        "id": "bp_simple_fact_registry",
        "name": "Static Fact Registry",
        "description": "Maintains read-only facts about system environment settings and operational environment variables.",
        "sections": ["core"],
        "overrides": {"core.crud_ops": {"auto_store": False}},
    },
    {
        "id": "bp_simple_qa_ref",
        "name": "Read-Only Q&A Reference",
        "description": "Connects to a local SQLite instance to serve product FAQ entries and static search tables.",
        "sections": ["storage"],
        "overrides": {"storage.cache_config": {"enabled": False}},
    },

    # ── Medium (3-4 sections enabled) ──
    {
        "id": "bp_medium_cust_support",
        "name": "Customer Support Bot",
        "description": "PII-redacted customer service memory. Combines core preferences with ticket history context.",
        "sections": ["core", "context", "retrieval", "security"],
        "overrides": {"security.pii_redaction": {"enabled": True, "auto_redact": True}},
    },
    {
        "id": "bp_medium_sem_clustering",
        "name": "Semantic Clustering Hub",
        "description": "Runs periodic K-Means clustering on vector data to discover emergent topics and semantic patterns.",
        "sections": ["core", "storage", "semantics"],
        "overrides": {"semantics.clustering": {"enabled": True, "algorithm": "kmeans", "n_clusters": 8}},
    },
    {
        "id": "bp_medium_spaced_rep",
        "name": "Spaced Repetition Tutor",
        "description": "Tutor system utilizing forgetting curves to adapt review intervals based on learning history.",
        "sections": ["core", "context", "adaptation"],
        "overrides": {"adaptation.reflection": {"enabled": True, "trigger": "interval", "interval_minutes": 15}},
    },
    {
        "id": "bp_medium_shared_pool",
        "name": "Collaborative Shared Pool",
        "description": "Federated shared memory pool allowing multiple agents to sync preferences with collision checks.",
        "sections": ["core", "storage", "federation"],
        "overrides": {"federation.sync_config": {"enabled": True, "sync_interval": 10, "direction": "bidirectional"}},
    },
    {
        "id": "bp_medium_secure_locker",
        "name": "Secure Document Locker",
        "description": "Encrypted memory partition enforcing key rotations and soft deletes for document privacy.",
        "sections": ["core", "storage", "security"],
        "overrides": {"security.encryption": {"enabled": True, "algorithm": "fernet", "key_rotation_days": 30}},
    },
    {
        "id": "bp_medium_db_bridge",
        "name": "Relational Database Bridge",
        "description": "Synchronizes memory stores with active relational SQL tables via incremental sync batches.",
        "sections": ["core", "storage", "retrieval"],
        "overrides": {"core.storage_config": {"adapter": "relational", "batch_size": 250}},
    },
    {
        "id": "bp_medium_code_reviewer",
        "name": "Code Review Assistant",
        "description": "Tracks git commits and file histories to remember coding patterns and past PR suggestions.",
        "sections": ["core", "context", "versioning"],
        "overrides": {"versioning.version_config": {"enabled": True, "max_versions": 15}},
    },
    {
        "id": "bp_medium_npc_personality",
        "name": "NPC Personality Brain",
        "description": "Maintains character memory logs, dialogue history, and dynamic relationship metrics.",
        "sections": ["core", "context", "adaptation", "persona"],
        "overrides": {"adaptation.reflection": {"enabled": True, "trigger": "session_end"}},
    },
    {
        "id": "bp_medium_adaptive_ui",
        "name": "Adaptive Dashboard Preferences",
        "description": "Adapts widget positions and theme styling based on user interaction metrics and window stats.",
        "sections": ["core", "context", "adaptation"],
        "overrides": {"adaptation.reinforcement": {"enabled": True, "learning_rate": 0.05}},
    },
    {
        "id": "bp_medium_iot_monitor",
        "name": "IoT Event Monitor",
        "description": "Ingests time-series metrics from sensor endpoints and logs deviations from baseline telemetry.",
        "sections": ["core", "storage", "observability"],
        "overrides": {"observability.health": {"enabled": True, "interval_seconds": 10}},
    },

    # ── Complex (5-6 sections enabled) ──
    {
        "id": "bp_complex_causal_graph",
        "name": "Causal Graphing Engine",
        "description": "Builds causal dependency diagrams and evaluates reasoning paths using semantic relationships.",
        "sections": ["core", "semantics", "causal", "strategy"],
        "overrides": {"strategy.goals": {"enabled": True, "max_goals": 5}},
    },
    {
        "id": "bp_complex_fed_sync",
        "name": "Federated Cross-Sync Engine",
        "description": "Enterprise multi-datacenter synchronized federation with digital signatures and TLS handshakes.",
        "sections": ["core", "security", "federation", "versioning"],
        "overrides": {"federation.sync_config": {"enabled": True, "direction": "bidirectional"}, "security.encryption": {"enabled": True}},
    },
    {
        "id": "bp_complex_cost_retriever",
        "name": "Cost-Aware Query Retriever",
        "description": "Saves tokens by dynamically scaling search top-k based on budget usage metrics.",
        "sections": ["retrieval", "economics", "observability"],
        "overrides": {"economics.cost_tracking": {"enabled": True, "period": "daily"}, "retrieval.text_search": {"default_top_k": 3}},
    },
    {
        "id": "bp_complex_self_reflector",
        "name": "Self-Reflective Knowledge Syncer",
        "description": "Runs background consolidation tasks to summarize experiences and prune obsolete entries.",
        "sections": ["core", "semantics", "adaptation", "working"],
        "overrides": {"adaptation.reflection": {"enabled": True, "trigger": "interval", "interval_minutes": 60}},
    },
    {
        "id": "bp_complex_medical_audit",
        "name": "Immutable Medical Audit Trail",
        "description": "HIPAA-compliant document management featuring zero-knowledge proof tokens and immutable logging.",
        "sections": ["core", "storage", "security", "observability", "audit"],
        "overrides": {"security.gdpr": {"consent_tracking": True}, "security.encryption": {"enabled": True}},
    },
    {
        "id": "bp_complex_multimodal_gallery",
        "name": "Multi-Modal CLIP Search Gallery",
        "description": "Processes and indexes text-image embeddings to enable search across heterogeneous documents.",
        "sections": ["core", "storage", "retrieval", "multimodal"],
        "overrides": {"retrieval.vector_search": {"embedding_model": "all-mpnet-base-v2"}},
    },
    {
        "id": "bp_complex_spatiotemporal",
        "name": "Spatio-Temporal Case Engine",
        "description": "Organizes events in geographical grids and sequence timelines to construct spatial history graphs.",
        "sections": ["core", "context", "retrieval", "causal"],
        "overrides": {"context.context_build": {"strategy": "importance_ranked"}},
    },
    {
        "id": "bp_complex_bandit_opt",
        "name": "Bandit-Optimized Personalizer",
        "description": "Learns context weights using multi-armed bandits to dynamic sort preference priorities.",
        "sections": ["core", "adaptation", "strategy", "economics", "bandit"],
        "overrides": {"bandit.bandit_config": {"enabled": True, "algorithm": "thompson"}},
    },
    {
        "id": "bp_complex_git_brancher",
        "name": "Git-Style Memory Brancher",
        "description": "Enables memory branching (checkout, commit, merge, diff) to test speculative scenarios.",
        "sections": ["core", "versioning", "federation", "testing"],
        "overrides": {"versioning.version_config": {"enabled": True, "max_versions": 50}},
    },
    {
        "id": "bp_complex_ontology_classifier",
        "name": "Ontological Entity Classifier",
        "description": "Maps memories to structured entity classes and asserts inheritance rules using type registries.",
        "sections": ["core", "semantics", "mql", "causal"],
        "overrides": {"mql.mql_config": {"enabled": True, "max_complexity": 25}},
    },

    # ── Comprehensive (7+ sections enabled) ──
    {
        "id": "bp_comprehensive_ent_core",
        "name": "Enterprise Cognitive Core",
        "description": "All-in-one cognitive engine. Hybrid storage adapters, PII redaction, self-reflection, and version histories.",
        "sections": ["core", "context", "storage", "retrieval", "semantics", "security", "economics", "versioning", "observability"],
        "overrides": {"core.storage_config": {"adapter": "pgvector"}, "security.encryption": {"enabled": True}, "economics.cost_tracking": {"enabled": True}},
    },
    {
        "id": "bp_comprehensive_fin_brain",
        "name": "Financial Volatility Forecast Brain",
        "description": "Monitors tick updates, generates vol forecasts, and evaluates trading paths under strict budgets.",
        "sections": ["core", "storage", "retrieval", "forecasting", "economics", "causal", "observability", "strategy"],
        "overrides": {"forecasting.recall_prediction": {"enabled": True, "model": "neural"}, "economics.cost_tracking": {"enabled": True}},
    },
    {
        "id": "bp_comprehensive_smart_city",
        "name": "Smart City Logistics Optimizer",
        "description": "Coordinates edge node sensors with centralized routing algorithms to plan optimal dispatch timings.",
        "sections": ["core", "context", "storage", "semantics", "forecasting", "adaptation", "federation", "observability"],
        "overrides": {"federation.sync_config": {"enabled": True}, "adaptation.reflection": {"enabled": True}},
    },
    {
        "id": "bp_comprehensive_clinical_cohort",
        "name": "Clinical Cohort Graph Compiler",
        "description": "Synthesizes patient histories to build symptom networks while ensuring HIPAA audit trails.",
        "sections": ["core", "storage", "retrieval", "semantics", "security", "causal", "mql", "observability"],
        "overrides": {"security.encryption": {"enabled": True}, "mql.mql_config": {"enabled": True}},
    },
    {
        "id": "bp_comprehensive_ecom_graph",
        "name": "Global E-Commerce Recommendation Graph",
        "description": "Learns cross-market shopping sequences, forecasts churn, and tunes recommendations via bandit nodes.",
        "sections": ["core", "context", "storage", "retrieval", "forecasting", "adaptation", "economics", "semantics", "bandit"],
        "overrides": {"bandit.bandit_config": {"enabled": True}, "adaptation.reinforcement": {"enabled": True}},
    },
    {
        "id": "bp_comprehensive_web3_trust",
        "name": "Web3 Cryptographic Trust Store",
        "description": "IPFS database adapters with AES-GCM local encryption and zero-knowledge identity validations.",
        "sections": ["core", "storage", "security", "versioning", "federation", "strategy", "causal"],
        "overrides": {"security.encryption": {"enabled": True, "algorithm": "aes256"}},
    },
    {
        "id": "bp_comprehensive_siem_hunter",
        "name": "Security SIEM Threat Hunter",
        "description": "Real-time log ingestion correlating telemetry alerts with historical attack sequences.",
        "sections": ["core", "retrieval", "semantics", "security", "forecasting", "observability", "testing", "causal"],
        "overrides": {"security.pii_redaction": {"enabled": True}, "observability.health": {"enabled": True}},
    },
    {
        "id": "bp_comprehensive_curriculum_tutor",
        "name": "Adaptive Tutor Curriculum Engine",
        "description": "Adapts student skill trees, scores cognitive load, and runs automated question validation trials.",
        "sections": ["core", "context", "semantics", "adaptation", "strategy", "testing", "persona", "observability"],
        "overrides": {"adaptation.reinforcement": {"enabled": True}},
    },
    {
        "id": "bp_comprehensive_swarm_manager",
        "name": "Autonomous Agent Swarm Manager",
        "description": "Synchronizes memory branches across dynamic worker threads using blackboard protocols.",
        "sections": ["core", "context", "semantics", "strategy", "federation", "versioning", "observability", "working"],
        "overrides": {"federation.sync_config": {"enabled": True}, "versioning.version_config": {"enabled": True}},
    },
    {
        "id": "bp_comprehensive_legal_graph",
        "name": "Case Analyzer & Citations Graph",
        "description": "Parses legal briefs, compiles citation networks, and logs immutable access histories for auditing.",
        "sections": ["core", "storage", "retrieval", "semantics", "security", "causal", "versioning", "mql"],
        "overrides": {"security.encryption": {"enabled": True}, "mql.mql_config": {"enabled": True}},
    },
]


def build_section_config(section_ids: list[str], overrides: dict = None) -> dict:
    """Build a Creator-style sections dict with given sections enabled and custom overrides."""
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
    if overrides:
        for key, value in overrides.items():
            if "." in key:
                section_id, sub_id = key.split(".", 1)
                if section_id in config:
                    if "subsections" not in config[section_id]:
                        config[section_id]["subsections"] = {}
                    if sub_id not in config[section_id]["subsections"]:
                        config[section_id]["subsections"][sub_id] = {"fields": {}}
                    for field_id, val in value.items():
                        config[section_id]["subsections"][sub_id]["fields"][field_id] = {
                            "value": val
                        }
            elif key in config:
                config[key].update(value)
    return config


def seed():
    with next(get_session()) as session:
        # Clear old seed data
        for r in session.exec(
            select(CompositionRecord).where(CompositionRecord.id.like("comp_bp_%"))
        ).all():
            session.delete(r)
        for r in session.exec(
            select(BlueprintRecord).where(BlueprintRecord.id.like("bp_%"))
        ).all():
            session.delete(r)
        session.commit()
        logger.info("Cleared previous seed data")

        now = datetime.now(timezone.utc).isoformat()
        total_blocks = 0

        for s in SCENARIOS:
            sections_dict = build_section_config(s["sections"], s.get("overrides"))
            
            # Blueprint
            bp = BlueprintRecord(
                id=s["id"],
                name=s["name"],
                description=s["description"],
                entity_type="memory",
                sections=json.dumps(sections_dict),
                created_at=now,
                updated_at=now,
            )
            session.add(bp)

            # Resolve blocks
            block_ids = sorted(
                {bid for sid in s["sections"] for bid in SECTION_BLOCK_MAP.get(sid, [])}
            )

            # Composition
            comp = CompositionRecord(
                id=f"comp_{s['id']}",
                name=f"Deployed: {s['name']}",
                description=f"Auto-deployed from {s['id']} — {s['description']}",
                block_ids=json.dumps(block_ids),
                source="scenario_seed",
                blueprint_id=s["id"],
                created_at=now,
                updated_at=now,
            )
            session.add(comp)

            logger.info(
                f"  ✅ {s['id']:40s} -> {len(block_ids):2d} blocks  ({', '.join(s['sections'])})"
            )

        session.commit()

    print(f"\nSeeded {len(SCENARIOS)} scenarios. Query them:")
    print(
        "  curl http://localhost:8000/api/v1/memory/blueprints  | jq '.blueprints | length'"
    )
    print(
        "  curl http://localhost:8000/api/v1/memory/compositions | jq '.compositions | length'"
    )


if __name__ == "__main__":
    seed()
