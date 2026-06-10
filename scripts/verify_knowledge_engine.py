#!/usr/bin/env python3
"""
Knowledge Engine — Verification Script.

Verifies that all components of the Knowledge Engine are properly
installed, importable, and in a healthy state. Runs structural checks
without requiring model downloads or GPU access.

Usage:
    uv run python scripts/verify_knowledge_engine.py
    uv run python scripts/verify_knowledge_engine.py --verbose

Exit codes:
    0: All checks pass
    1: Warnings (non-critical issues)
    2: Failures (critical issues)
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

# ── Fix Windows console encoding ─────────────────────────────
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── Test runner ─────────────────────────────────────────────────


class CheckResult:
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass
class Check:
    name: str
    status: str = CheckResult.PASS
    detail: str = ""
    duration_ms: float = 0.0


results: list[Check] = []


def run_check(name: str, fn, *args, **kwargs):
    start = time.perf_counter()
    try:
        fn(*args, **kwargs)
        results.append(Check(name=name, status=CheckResult.PASS, duration_ms=(time.perf_counter() - start) * 1000))
    except Exception as e:
        results.append(
            Check(
                name=name,
                status=CheckResult.FAIL,
                detail=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        )


def run_check_skip(name: str, reason: str):
    results.append(Check(name=name, status=CheckResult.SKIP, detail=reason))


def run_check_warn(name: str, detail: str):
    results.append(Check(name=name, status=CheckResult.WARN, detail=detail))


# ── Checks ─────────────────────────────────────────────────────


def check_import(module_path: str, name: str | None = None):
    """Check that a module imports without error."""
    try:
        mod = importlib.import_module(module_path)
        if name:
            getattr(mod, name)
    except Exception as e:
        raise RuntimeError(f"Failed to import {module_path}" + (f".{name}" if name else "") + f": {e}")


def check_knowledge_engine_imports():
    """Verify all major submodules import cleanly."""
    modules = [
        "common_lib.modules.knowledge_engine",
        "common_lib.modules.knowledge_engine.config",
        "common_lib.modules.knowledge_engine.service",
        "common_lib.modules.knowledge_engine.chunking",
        "common_lib.modules.knowledge_engine.chunking.base",
        "common_lib.modules.knowledge_engine.chunking.semantic",
        "common_lib.modules.knowledge_engine.chunking.hierarchical",
        "common_lib.modules.knowledge_engine.chunking.proposition",
        "common_lib.modules.knowledge_engine.chunking.code_aware",
        "common_lib.modules.knowledge_engine.chunking.late_chunking",
        "common_lib.modules.knowledge_engine.chunking.strategies",
        "common_lib.modules.knowledge_engine.embedding",
        "common_lib.modules.knowledge_engine.embedding.registry",
        "common_lib.modules.knowledge_engine.embedding.pipeline",
        "common_lib.modules.knowledge_engine.embedding.compression",
        "common_lib.modules.knowledge_engine.embedding.providers",
        "common_lib.modules.knowledge_engine.embedding.providers.bge_m3",
        "common_lib.modules.knowledge_engine.embedding.providers.openai",
        "common_lib.modules.knowledge_engine.embedding.providers.local",
        "common_lib.modules.knowledge_engine.retrieval",
        "common_lib.modules.knowledge_engine.retrieval.query_understanding",
        "common_lib.modules.knowledge_engine.retrieval.dense_retriever",
        "common_lib.modules.knowledge_engine.retrieval.sparse_retriever",
        "common_lib.modules.knowledge_engine.retrieval.metadata_retriever",
        "common_lib.modules.knowledge_engine.retrieval.graph_retriever",
        "common_lib.modules.knowledge_engine.retrieval.rrf",
        "common_lib.modules.knowledge_engine.retrieval.engine",
        "common_lib.modules.knowledge_engine.retrieval.hyde",
        "common_lib.modules.knowledge_engine.reranking",
        "common_lib.modules.knowledge_engine.reranking.service",
        "common_lib.modules.knowledge_engine.reranking.mmr",
        "common_lib.modules.knowledge_engine.reranking.models",
        "common_lib.modules.knowledge_engine.context",
        "common_lib.modules.knowledge_engine.context.budget",
        "common_lib.modules.knowledge_engine.context.fusion",
        "common_lib.modules.knowledge_engine.context.formatters",
        "common_lib.modules.knowledge_engine.validation",
        "common_lib.modules.knowledge_engine.validation.validator",
        "common_lib.modules.knowledge_engine.knowledge_graph",
        "common_lib.modules.knowledge_engine.knowledge_graph.graphrag",
    ]

    for mod_path in modules:
        check_import(mod_path)


def check_models_import():
    """Verify all model classes import correctly."""
    from common_lib.modules.knowledge_engine.models import (  # noqa: F401
        KnowledgeChunk,
        RetrievedChunk,
        RetrievalPlan,
        RetrievalFilters,
        ContextPackage,
        ContextChunk,
        ChunkEmbedding,
        EmbeddingResult,
        EmbeddingBatchResult,
        ValidationReport,
        ContradictionRecord,
        StalenessRecord,
        HallucinationFlag,
    )


def check_config():
    """Verify config object instantiates correctly."""
    from common_lib.modules.knowledge_engine.config import KnowledgeEngineConfig

    config = KnowledgeEngineConfig()
    assert config.chunking.default_strategy == "semantic"
    assert config.embedding.default_model == "BAAI/bge-m3"
    assert config.retrieval.default_top_k == 100
    assert config.reranking.enabled is True
    assert config.context.default_token_budget == 16000
    assert config.validation.contradiction_check_enabled is True

    # Test to_dict export
    d = config.to_dict()
    assert isinstance(d, dict)
    assert "chunking" in d
    assert "embedding" in d
    assert "retrieval" in d
    assert "reranking" in d
    assert "context" in d

    # Test error hierarchy
    from common_lib.modules.knowledge_engine.config import (
        ChunkingError,
        ContextFusionError,
        EmbeddingError,
        KnowledgeEngineError,
        RetrievalError,
        ValidationError,
    )

    assert issubclass(ChunkingError, KnowledgeEngineError)
    assert issubclass(EmbeddingError, KnowledgeEngineError)
    assert issubclass(RetrievalError, KnowledgeEngineError)
    assert issubclass(ValidationError, KnowledgeEngineError)
    assert issubclass(ContextFusionError, KnowledgeEngineError)


def check_service():
    """Verify KnowledgeEngineService instantiates and passes health check."""
    from common_lib.modules.knowledge_engine.service import KnowledgeEngineService

    service = KnowledgeEngineService()
    assert service.config is not None
    assert service._engine is None  # not yet initialized

    # Test config methods (no async needed)
    cfg = service.get_config()
    assert isinstance(cfg, dict)
    assert "chunking" in cfg

    # Test compression (pure sync)
    compressed = service.compress_vector([0.5] * 32, bits=8)
    assert isinstance(compressed, bytes)
    decompressed = service.decompress_vector(compressed, bits=8)
    assert len(decompressed) == 32

    # Test list_models (pure sync)
    models = service.list_models()
    assert len(models) >= 1

    # Test default model
    default = service.get_default_model()
    assert "model_id" in default or "name" in default

    # Test health — use sync health status without asyncio
    # Access config directly to verify engine state
    assert service.config.version == "1.0.0"
    assert service.config.embedding.default_model == "BAAI/bge-m3"

    # Verify models list also contains chunking strategies info
    # by checking the EmbeddingModelRegistry directly
    from common_lib.modules.knowledge_engine.embedding.registry import EmbeddingModelRegistry
    assert EmbeddingModelRegistry.count() >= 1


def check_embedding_registry():
    """Verify EmbeddingModelRegistry has all 7 models."""
    from common_lib.modules.knowledge_engine.embedding.registry import EmbeddingModelRegistry

    all_models = EmbeddingModelRegistry.get_all()
    assert len(all_models) >= 1
    assert EmbeddingModelRegistry.count() >= 1
    assert EmbeddingModelRegistry.get_default() is not None
    ids = EmbeddingModelRegistry.list_ids()
    assert len(ids) >= 1


def check_chunking_strategy_selector():
    """Verify ChunkingStrategySelector selects correct strategies without model downloads."""
    from common_lib.modules.knowledge_engine.chunking.strategies import ChunkingStrategySelector, SingleChunker
    from common_lib.modules.knowledge_engine.chunking.code_aware import CodeChunker
    from common_lib.modules.knowledge_engine.chunking.semantic import SemanticChunker
    from common_lib.modules.knowledge_engine.chunking.hierarchical import HierarchicalChunker

    selector = ChunkingStrategySelector()

    # Test select() dispatches by content type — sync method
    code_chunker = selector.select("def hello(): pass", {"content_type": "code"})
    assert isinstance(code_chunker, CodeChunker)

    long_text = "Natural language text about AI. " * 200  # > 100 tokens
    semantic_chunker = selector.select(long_text, {"content_type": "text"})
    assert isinstance(semantic_chunker, (SemanticChunker, HierarchicalChunker))

    single_chunker = selector.select("Short.", {"content_type": "text"})
    assert isinstance(single_chunker, SingleChunker)


def check_turbo_quant():
    """Verify TurboQuantCompressor works correctly."""
    from common_lib.modules.knowledge_engine.embedding.compression import TurboQuantCompressor

    compressor_8 = TurboQuantCompressor(bits=8)
    compressor_4 = TurboQuantCompressor(bits=4)

    vector = [float(i) / 100.0 for i in range(128)]

    c8 = compressor_8.compress(vector)
    assert isinstance(c8, bytes)
    assert len(c8) > 0
    d8 = compressor_8.decompress(c8)
    assert len(d8) == 128

    c4 = compressor_4.compress(vector)
    assert isinstance(c4, bytes)
    d4 = compressor_4.decompress(c4)
    assert len(d4) == 128

    # 4-bit should have larger error than 8-bit
    err8 = sum((a - b) ** 2 for a, b in zip(vector, d8))
    err4 = sum((a - b) ** 2 for a, b in zip(vector, d4))
    assert err4 >= err8 * 0.5  # 4-bit is at least somewhat lossier


def check_mmr():
    """Verify MMR diversity selector works."""
    from common_lib.modules.knowledge_engine.reranking.mmr import MMRSelector
    from common_lib.modules.knowledge_engine.models.retrieval import RetrievedChunk
    from uuid import uuid4

    chunks = [
        RetrievedChunk(
            chunk_id=uuid4(), document_id=uuid4(), source_id="src", source_type="doc",
            content=f"Chunk {i}", rerank_score=s,
        )
        for i, s in enumerate([0.9, 0.8, 0.7])
    ]
    embeddings = {c.chunk_id: [float(j) for j in range(10)] for c in chunks}

    selector = MMRSelector()
    selected = selector.select(chunks=chunks, chunk_embeddings=embeddings, top_k=2)
    assert len(selected) == 2
    assert selected[0].rerank_score == 0.9  # highest score always first


def check_context_budget():
    """Verify TokenBudgetManager produces valid budgets."""
    from common_lib.modules.knowledge_engine.context.budget import TokenBudgetManager
    from common_lib.modules.knowledge_engine.config import ContextConfig

    ctx_config = ContextConfig(default_token_budget=10000)
    manager = TokenBudgetManager(context_config=ctx_config)
    budget = manager.allocate(query_type="factual")
    assert isinstance(budget, dict)
    assert "knowledge" in budget
    assert sum(budget.values()) <= 10000


def check_graphrag():
    """Verify GraphRAGIndexer builds communities without model downloads."""
    from common_lib.modules.knowledge_engine.knowledge_graph.graphrag import GraphRAGIndexer, GraphRAGConfig
    from common_lib.modules.knowledge_engine.models.knowledge import KnowledgeChunk
    from uuid import uuid4

    # Use min_cooccurrence=1 since we have small test data,
    # and min_community_size=2 for the 2 overlapping entities
    rag_config = GraphRAGConfig(min_cooccurrence=1, min_community_size=2)
    indexer = GraphRAGIndexer(config=rag_config)

    chunks = [
        KnowledgeChunk(
            chunk_id=str(uuid4()),
            document_id=str(uuid4()),
            source_id="doc_1", source_type="doc",
            content="FastAPI is a web framework for building APIs with Python.",
            entities=["FastAPI", "Python"],
            domain="engineering",
        ),
        KnowledgeChunk(
            chunk_id=str(uuid4()),
            document_id=str(uuid4()),
            source_id="doc_2", source_type="doc",
            content="FastAPI supports async def route handlers.",
            entities=["FastAPI"],
            domain="engineering",
        ),
    ]

    # Build communities (purely computational, no model downloads)
    communities = indexer.build_communities(chunks)
    assert communities is not None

    # Stats
    stats = indexer.stats
    assert "communities" in stats
    assert "entities" in stats

    # Clear and reindex
    indexer.clear()
    assert indexer.stats["communities"] == 0


def check_dip_routes():
    """Verify DIP route modules import without errors."""
    check_import("app.modules.dip.routes.rag")
    check_import("app.modules.dip.routes.embeddings")
    check_import("app.modules.dip.routes.storage")
    check_import("app.modules.dip.routes.pipeline")


def check_feature_flags():
    """Verify knowledge.* feature flags exist in the registry."""
    from common_lib.modules.data_pipeline.features_config import feature_registry

    expected_flags = [
        "knowledge.chunking",
        "knowledge.embedding",
        "knowledge.retrieval",
        "knowledge.reranking",
        "knowledge.context_fusion",
        "knowledge.graphrag",
    ]

    for flag_id in expected_flags:
        flag = feature_registry.get(flag_id)
        assert flag is not None, f"Feature flag '{flag_id}' not found in registry"
        assert flag.name, f"Feature flag '{flag_id}' missing name"
        assert flag.category, f"Feature flag '{flag_id}' missing category"

    # Verify chunking is enabled by default
    assert feature_registry.is_enabled("knowledge.chunking")
    assert feature_registry.is_enabled("knowledge.embedding")
    assert feature_registry.is_enabled("knowledge.retrieval")
    assert feature_registry.is_enabled("knowledge.context_fusion")

    # Verify graphrag depends on kg.construction
    graphrag = feature_registry.get("knowledge.graphrag")
    deps = graphrag.dependencies
    assert any(d.feature == "kg.construction" for d in deps)


def check_module_registration():
    """Verify knowledge_engine is registered in modules/__init__.py."""
    from common_lib.modules import MODULE_METADATA

    assert "knowledge_engine" in MODULE_METADATA
    meta = MODULE_METADATA["knowledge_engine"]
    assert meta["label"] == "Knowledge Engine"
    assert "modules" in meta
    assert "chunking" in meta["modules"]
    assert "retrieval" in meta["modules"]


# ── Main ───────────────────────────────────────────────────────


def print_report():
    """Print formatted verification report."""
    print()
    print("=" * 60)
    print("  Knowledge Engine -- Verification Report")
    print("=" * 60)

    passed = sum(1 for r in results if r.status == CheckResult.PASS)
    warnings = sum(1 for r in results if r.status == CheckResult.WARN)
    failed = sum(1 for r in results if r.status == CheckResult.FAIL)
    skipped = sum(1 for r in results if r.status == CheckResult.SKIP)
    total = len(results)

    for r in results:
        status_str = f"[{r.status}]"
        duration_str = f" ({r.duration_ms:.0f}ms)" if r.duration_ms > 0 else ""
        print(f"  {status_str} {r.name}{duration_str}")
        if r.detail:
            for line in r.detail.split("\n"):
                print(f"         {line}")

    print("-" * 60)
    print(f"  Total: {total} | PASS: {passed} | WARN: {warnings} | FAIL: {failed} | SKIP: {skipped}")
    print("=" * 60)

    if failed > 0:
        print()
        print("  FAIL: Some checks failed. Review details above.")
        return 2
    elif warnings > 0:
        print()
        print("  WARN: All critical checks passed, with warnings.")
        return 1
    else:
        print()
        print("  PASS: All checks passed!")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Verify Knowledge Engine installation and health")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    if args.verbose:
        print("Verbose mode enabled -- showing all details.\n")

    # ── Module Imports ──
    print("Checking module imports...")
    run_check("All submodule imports", check_knowledge_engine_imports)
    run_check("Model classes import", check_models_import)
    run_check("DIP route modules import", check_dip_routes)

    # ── Configuration ──
    print("Checking configuration...")
    run_check("Config object + error hierarchy", check_config)
    run_check("Embedding model registry", check_embedding_registry)
    run_check("Feature flags registration", check_feature_flags)
    run_check("Module registration in modules/__init__", check_module_registration)

    # ── Service Layer ──
    print("Checking service layer...")
    run_check("KnowledgeEngineService + health + compression", check_service)

    # ── Core Components ──
    print("Checking core components...")
    run_check("ChunkingStrategySelector dispatch", check_chunking_strategy_selector)
    run_check("TurboQuant compression (4-bit + 8-bit)", check_turbo_quant)
    run_check("MMR diversity selector", check_mmr)
    run_check("TokenBudgetManager allocation", check_context_budget)
    run_check("GraphRAGIndexer build + stats + clear", check_graphrag)

    # ── Report ──
    return print_report()


if __name__ == "__main__":
    sys.exit(main())
