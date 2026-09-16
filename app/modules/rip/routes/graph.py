"""RIP Graph routes — Knowledge graph construction, search, and GraphRAG.

Implements endpoints 11.15–11.17 from the implementation tracker.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from common_lib.modules.rip.rip_graph.schemas import (
    GraphSearchRequest,
    GraphSearchResponse,
    GraphBuildRequest,
    GraphRAGRequest,
    GraphRAGResponse,
    GraphNode,
    GraphEdge,
)

router = APIRouter(prefix="/rip/graph", tags=["RIP — Graph Intelligence"])


# --- Nexus Wave 3 (C028 ext, SSOT §16): optional `channels` query param -------
# Mirror of the search.py hook (kept local so route modules stay decoupled).
# Absent → existing behavior byte-identical. Present → validated against the
# 10 C022 channels (400 on unknown, 503 when the channels flag is off).


def _validate_graph_channels_param(channels: Optional[str]) -> Optional[list[str]]:
    """Validate an optional comma-separated §16 channel list (C028)."""
    if channels is None or not channels.strip():
        return None
    from common_lib.modules.rip.feature_flags import is_enabled
    from common_lib.modules.rip.rip_retrieval.channels import CHANNELS

    if not is_enabled("NEXUS_RETRIEVAL_CHANNELS_ENABLED"):
        raise HTTPException(
            status_code=503, detail="NEXUS_RETRIEVAL_CHANNELS_ENABLED is off"
        )
    selected = [c.strip().lower() for c in channels.split(",") if c.strip()]
    unknown = [c for c in selected if c not in CHANNELS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"unknown retrieval channels: {unknown}; valid: {list(CHANNELS)}",
        )
    return selected


@router.post("/search", response_model=GraphSearchResponse)
async def graph_search(
    payload: GraphSearchRequest,
    channels: Optional[str] = Query(
        default=None,
        description=(
            "Optional comma-separated SSOT §16 retrieval-channel subset "
            "(10 C022 channels). Absent = existing behavior."
        ),
    ),
):
    """Search the knowledge graph — traverses entities and relationships."""
    _validate_graph_channels_param(channels)
    try:
        from common_lib.modules.rip.rip_graph.service import search_graph
        import time

        start = time.perf_counter()
        result = await search_graph(
            query=payload.query,
            entity_types=payload.entity_types,
            max_hops=payload.max_hops,
            top_k=payload.top_k,
            tenant_id=payload.tenant_id,
        )
        return GraphSearchResponse(
            nodes=[
                GraphNode(**n) if isinstance(n, dict) else n
                for n in result.get("nodes", [])
            ],
            edges=[
                GraphEdge(**e) if isinstance(e, dict) else e
                for e in result.get("edges", [])
            ],
            query=payload.query,
            subgraph=result.get("subgraph"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/build")
async def build_knowledge_graph(payload: GraphBuildRequest):
    """Build or update a knowledge graph from document entities."""
    try:
        from common_lib.modules.rip.rip_graph.service import build_graph

        result = await build_graph(
            document_ids=payload.document_ids,
            entity_extraction_model=payload.entity_extraction_model,
            extract_relationships=payload.relationship_extraction,
            max_entities=payload.max_entities,
            tenant_id=payload.tenant_id,
        )
        return {
            "graph_id": result.get("graph_id"),
            "node_count": result.get("node_count", 0),
            "edge_count": result.get("edge_count", 0),
            "documents_processed": len(payload.document_ids),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/graphrag", response_model=GraphRAGResponse)
async def graph_rag_query(payload: GraphRAGRequest):
    """GraphRAG query — dual-channel retrieval over vector + graph indexes.

    Methods: graphrag, lightrag, hybrid, kg_traversal.
    Uses the GraphRAG connector for real graph operations.
    """
    try:
        from common_lib.modules.rip.rip_connectors import create_graphrag_fn
        import time

        start = time.perf_counter()
        graphrag_fn = await create_graphrag_fn(
            method=payload.method or "graphrag",
        )
        result = await graphrag_fn(
            query=payload.query,
            top_k=payload.top_k,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return GraphRAGResponse(
            results=result.get("results", []),
            graph_context=result.get("graph_context"),
            community_summaries=result.get("community_summaries"),
            total_time_ms=elapsed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Nexus Wave 3 (C028, SSOT §19/P0#5#6): entity/event channel endpoints -----
# Thin delegation to common_lib C024 functions; stateless (inline inventories).


@router.post("/entity-channel", response_model=dict)
async def entity_channel(payload: dict):
    """Entity-centric retrieval (§19/P0#5) over inline inventories."""
    try:
        from common_lib.modules.rip.feature_flags import is_enabled
        from common_lib.modules.rip.rip_graph.entity_event_channels import (
            retrieve_entity_mentions,
        )

        if not is_enabled("NEXUS_RETRIEVAL_CHANNELS_ENABLED"):
            raise HTTPException(
                status_code=503, detail="NEXUS_RETRIEVAL_CHANNELS_ENABLED is off"
            )
        return retrieve_entity_mentions(
            payload.get("query", ""),
            inventories=payload.get("inventories"),
            entity_types=payload.get("entity_types"),
            top_k=int(payload.get("top_k", 10)),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/event-channel", response_model=dict)
async def event_channel(payload: dict):
    """Event-centric retrieval (§19/P0#6) over inline inventories."""
    try:
        from common_lib.modules.rip.feature_flags import is_enabled
        from common_lib.modules.rip.rip_graph.entity_event_channels import (
            retrieve_event_universe,
        )

        if not is_enabled("NEXUS_RETRIEVAL_CHANNELS_ENABLED"):
            raise HTTPException(
                status_code=503, detail="NEXUS_RETRIEVAL_CHANNELS_ENABLED is off"
            )
        return retrieve_event_universe(
            payload.get("query", ""),
            inventories=payload.get("inventories"),
            top_k=int(payload.get("top_k", 10)),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
