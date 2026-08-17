"""KPE Knowledge Graph Route — Thin FastAPI wrapper for KG operations.

Uses LLM-driven entity/relation extraction (LLMKnowledgeGraphService) with static fallback.
Set use_llm=false to use manual KnowledgeGraphBuilder directly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.kpe.knowledge_graph.llm import LLMKnowledgeGraphService
from common_lib.modules.knowledge_engine.kpe.knowledge_graph.analytics import analyze_graph

logger = logging.getLogger(__name__)

router = APIRouter()

_llm_kg_service = LLMKnowledgeGraphService()


class ExtractGraphRequest(BaseModel):
    """Request to extract a knowledge graph from text."""

    text: str = Field(description="Text to extract entities and relationships from")
    use_llm: bool = Field(default=True, description="Use LLM-driven extraction (falls back to keyword-based if unavailable)")


class GraphQueryRequest(BaseModel):
    """Request to query the knowledge graph."""

    entities: List[Dict[str, Any]] = Field(description="Extracted entities")
    relationships: List[Dict[str, Any]] = Field(description="Extracted relationships")
    query: str = Field(description="Natural language query about the graph")


class InferGraphRequest(BaseModel):
    """Request to infer relationships in the knowledge graph."""

    entities: List[Dict[str, Any]] = Field(description="Existing entities")
    relationships: List[Dict[str, Any]] = Field(description="Existing relationships")


@router.post("/extract")
async def extract_graph(payload: ExtractGraphRequest):
    """Extract entities and relationships from text using LLM."""
    try:
        result = _llm_kg_service.extract_from_text(payload.text)

        # Build NetworkX graph and get stats
        graph = _llm_kg_service.build_networkx(
            result.get("entities", []), result.get("relationships", [])
        )
        stats = analyze_graph(graph)

        return {
            "success": True,
            "engine": result.get("method", "llm"),
            "entities": result.get("entities", []),
            "relationships": result.get("relationships", []),
            "graph_summary": result.get("graph_summary", ""),
            "node_count": result.get("node_count", 0),
            "edge_count": result.get("edge_count", 0),
            "central_entities": result.get("central_entities", []),
            "stats": stats,
        }
    except Exception as e:
        logger.error("KG extraction failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/infer")
async def infer_relationships(payload: InferGraphRequest):
    """Infer new relationships from existing graph structure."""
    try:
        result = _llm_kg_service.infer_relationships(
            entities=payload.entities,
            relationships=payload.relationships,
        )
        return {
            "success": True,
            "inferred_relationships": result.get("inferred_relationships", []),
            "suggested_merges": result.get("suggested_merges", []),
            "reasoning_pattern": result.get("reasoning_pattern", ""),
        }
    except Exception as e:
        logger.error("KG inference failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query_graph(payload: GraphQueryRequest):
    """Answer a natural language query using the knowledge graph."""
    try:
        result = _llm_kg_service.query_graph(
            entities=payload.entities,
            relationships=payload.relationships,
            query=payload.query,
        )
        return {
            "success": True,
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence", 0.0),
            "path": result.get("path", []),
            "explanation": result.get("explanation", ""),
        }
    except Exception as e:
        logger.error("KG query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
