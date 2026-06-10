import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Query, HTTPException

from common_lib.modules.graph import GraphService, GraphNode, GraphEdge, GraphResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Graph"])

_svc = GraphService()


@router.get("/", response_model=GraphResponse)
async def get_graph(refresh: bool = Query(False)):
    return await _svc.load_graph(refresh)


@router.get("/nodes", response_model=Dict[str, Any])
async def get_graph_nodes():
    return await _svc.get_nodes()


@router.get("/node/{node_id}", response_model=GraphNode)
async def get_graph_node(node_id: str):
    return await _svc.get_node(node_id)


@router.get("/edges", response_model=List[GraphEdge])
async def get_graph_edges():
    return await _svc.get_edges()


@router.get("/search", response_model=Dict[str, Any])
async def search_graph(q: str = ""):
    return await _svc.search(q)


@router.post("/clear", response_model=Dict[str, str])
async def clear_graph(confirm: bool = Query(False)):
    return await _svc.clear_graph(confirm)


@router.post("/project", response_model=Dict[str, Any])
async def project_knowledgebase(entity_type: str = Query("knowledgebase")):
    return await _svc.project_knowledgebase()


@router.get("/stats", response_model=Dict[str, Any])
async def get_graph_stats():
    return await _svc.get_stats()
