"""RIP Graph routes — Knowledge graph construction, search, and GraphRAG.

Implements endpoints 11.15–11.17 from the implementation tracker.
"""

from fastapi import APIRouter, HTTPException

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


@router.post("/search", response_model=GraphSearchResponse)
async def graph_search(payload: GraphSearchRequest):
    """Search the knowledge graph — traverses entities and relationships."""
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
            nodes=[GraphNode(**n) if isinstance(n, dict) else n for n in result.get("nodes", [])],
            edges=[GraphEdge(**e) if isinstance(e, dict) else e for e in result.get("edges", [])],
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
