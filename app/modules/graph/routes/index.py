import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Query, HTTPException

from common_lib.modules.knowledge_engine.graph import GraphService, GraphNode, GraphEdge, GraphResponse

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


# ═══════════════════════════════════════════════════════════════════
# Entity CRUD
# ═══════════════════════════════════════════════════════════════════


@router.post("/nodes", response_model=GraphNode, status_code=201)
async def create_graph_node(node: GraphNode):
    return await _svc.create_node(node)


@router.put("/nodes/{node_id}", response_model=GraphNode)
async def update_graph_node(node_id: str, updates: Dict[str, Any]):
    return await _svc.update_node(node_id, updates)


@router.delete("/nodes/{node_id}", response_model=Dict[str, str])
async def delete_graph_node(node_id: str):
    return await _svc.delete_node(node_id)


@router.post("/edges", response_model=GraphEdge, status_code=201)
async def create_graph_edge(from_id: str = Query(...), to_id: str = Query(...), label: str = Query("RELATED")):
    return await _svc.create_edge(from_id, to_id, label)


@router.delete("/edges", response_model=Dict[str, str])
async def delete_graph_edge(from_id: str = Query(...), to_id: str = Query(...), label: str = Query("RELATED")):
    return await _svc.delete_edge(from_id, to_id, label)


# ═══════════════════════════════════════════════════════════════════
# Shortest Path / Communities / Export
# ═══════════════════════════════════════════════════════════════════


@router.get("/shortest-path", response_model=Dict[str, Any])
async def get_shortest_path(
    from_id: str = Query(...), to_id: str = Query(...), max_depth: int = Query(6),
):
    return await _svc.shortest_path(from_id, to_id, max_depth)


@router.get("/communities", response_model=Dict[str, Any])
async def get_communities():
    return await _svc.get_communities()


@router.get("/export", response_model=Dict[str, Any])
async def export_graph(fmt: str = Query("json")):
    return await _svc.export_graph(fmt)


# ═══════════════════════════════════════════════════════════════════
# Provenance + ACL (NEX-P6-001) — thin routes, logic in common_lib.
# Mutations 404 while knowledge_engine.graph.provenance.enabled is OFF.
# ═══════════════════════════════════════════════════════════════════

_provenance_svc = None


def _provenance_service():
    global _provenance_svc
    if _provenance_svc is None:
        from common_lib.modules.knowledge_engine.graph.provenance.service import (
            ProvenanceGraphService,
        )

        _provenance_svc = ProvenanceGraphService()
    return _provenance_svc


def _provenance_principal(tenant: str):
    from common_lib.modules.knowledge_engine.graph.provenance.authz import Principal

    return Principal(tenant=tenant)


def _require_provenance_enabled():
    from fastapi import HTTPException

    from common_lib.modules.knowledge_engine.graph.provenance.flags import is_enabled

    if not is_enabled():
        raise HTTPException(status_code=404, detail="Provenance store disabled")


@router.post("/provenance/nodes", response_model=Dict[str, Any], status_code=201)
async def provenance_upsert_node(record: Dict[str, Any]):
    _require_provenance_enabled()
    from common_lib.modules.knowledge_engine.graph.provenance.models import (
        ProvenanceNode,
    )

    stored = _provenance_service().upsert_node(ProvenanceNode(**record))
    return stored.model_dump()


@router.post("/provenance/edges", response_model=Dict[str, Any], status_code=201)
async def provenance_upsert_edge(record: Dict[str, Any]):
    _require_provenance_enabled()
    from common_lib.modules.knowledge_engine.graph.provenance.models import (
        ProvenanceEdge,
    )

    stored = _provenance_service().upsert_edge(ProvenanceEdge(**record))
    return stored.model_dump()


@router.post("/provenance/reconcile", response_model=Dict[str, Any])
async def provenance_reconcile(payload: Dict[str, Any]):
    _require_provenance_enabled()
    from common_lib.modules.knowledge_engine.graph.provenance.models import (
        ProvenanceEdge,
        ProvenanceNode,
    )

    return _provenance_service().reconcile(
        tenant=payload.get("tenant", ""),
        source_system=payload.get("source_system", ""),
        nodes=[ProvenanceNode(**n) for n in payload.get("nodes", [])],
        edges=[ProvenanceEdge(**e) for e in payload.get("edges", [])],
        watermark=payload.get("watermark", ""),
    )


@router.get("/provenance/query", response_model=Dict[str, Any])
async def provenance_query(
    tenant: str = Query(...),
    mode: str = Query("nodes"),
    stable_id: str = Query(""),
    max_depth: int = Query(2),
):
    svc = _provenance_service()
    principal = _provenance_principal(tenant)
    if mode == "neighbourhood":
        return svc.neighbourhood(principal, stable_id, max_depth=max_depth)
    if mode == "edges":
        return {"edges": [e.model_dump() for e in svc.visible_edges(principal)]}
    return {"nodes": [n.model_dump() for n in svc.visible_nodes(principal)]}


@router.get("/provenance/completeness", response_model=Dict[str, Any])
async def provenance_completeness(tenant: str = Query("")):
    return _provenance_service().provenance_completeness(tenant or None)


@router.get("/provenance/staleness", response_model=Dict[str, Any])
async def provenance_staleness(tenant: str = Query("")):
    return _provenance_service().staleness_metrics(tenant or None)
