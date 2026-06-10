from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict, Any
from common_lib.modules.graph import GraphService

_graph_svc = GraphService()

router = APIRouter(prefix="/dip/kg", tags=["dip/kg"])

@router.get("/entities")
async def list_kg_entities(
    category: str = Query(None),
    refresh: bool = Query(False)
):
    """List knowledge graph entities (nodes)."""
    graph_data = await _graph_svc.load_graph(refresh=refresh)
    nodes = graph_data.nodes
    
    if category:
        nodes = [n for n in nodes if n.category.lower() == category.lower()]
        
    return {
        "data": [n.model_dump() for n in nodes],
        "count": len(nodes)
    }

@router.get("/relations")
async def list_kg_relations(refresh: bool = Query(False)):
    """List knowledge graph relations (edges)."""
    graph_data = await _graph_svc.load_graph(refresh=refresh)
    edges = graph_data.edges
    
    return {
        "data": [e.model_dump() for e in edges],
        "count": len(edges)
    }

@router.get("/metrics")
async def get_kg_metrics():
    """Get knowledge graph health and density metrics."""
    graph_data = await _graph_svc.load_graph()
    
    # Calculate density or other metrics if needed
    node_count = len(graph_data.nodes)
    edge_count = len(graph_data.edges)
    
    return {
        "data": {
            "total_entities": node_count,
            "total_relations": edge_count,
            "density": (edge_count / (node_count * (node_count - 1))) if node_count > 1 else 0,
            "categories": graph_data.categories,
            "summary": graph_data.summary
        }
    }
