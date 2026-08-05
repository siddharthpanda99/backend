"""Universal Work Graph REST routes.

Domain 00.04 — Universal Work Graph.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from common_lib.modules.project_management.universal_graph.service import WorkGraphService

from app.modules.auth.dependencies import require_permission
from app.modules.project_management.dependencies import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/graph/nodes")
def register_node(
    workspace_id: str,
    entity_type: str,
    entity_id: str,
    title: str = "",
    entity_data: Optional[dict] = None,
    _perm: None = require_permission("graph.create", "*", "graph"),
    session=Depends(get_db_session),
):
    """Register an entity as a graph node."""
    svc = WorkGraphService(session=session)
    node = svc.register_node(
        workspace_id=workspace_id, entity_type=entity_type,
        entity_id=entity_id, title=title, entity_data=entity_data,
    )
    return {"id": node.id, "entity_type": node.entity_type, "entity_id": node.entity_id, "version": node.version}


@router.delete("/graph/nodes/{entity_type}/{entity_id}")
def unregister_node(
    workspace_id: str,
    entity_type: str,
    entity_id: str,
    _perm: None = require_permission("graph.delete", "*", "graph"),
    session=Depends(get_db_session),
):
    """Remove a node and all its edges from the graph."""
    svc = WorkGraphService(session=session)
    success = svc.unregister_node(workspace_id=workspace_id, entity_type=entity_type, entity_id=entity_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Node {entity_type}:{entity_id} not found")
    return {"success": True}


@router.get("/graph/nodes")
def list_nodes(
    workspace_id: str,
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("graph.read", "*", "graph"),
    session=Depends(get_db_session),
):
    """List graph nodes, optionally filtered by entity type."""
    svc = WorkGraphService(session=session)
    nodes = svc.list_nodes(
        workspace_id=workspace_id, entity_type=entity_type,
        limit=limit, offset=offset,
    )
    return {"nodes": [n.model_dump() for n in nodes], "total": len(nodes)}


@router.post("/graph/edges")
def link_nodes(
    workspace_id: str,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    relationship: str = "relates_to",
    weight: float = 1.0,
    _perm: None = require_permission("graph.update", "*", "graph"),
    session=Depends(get_db_session),
):
    """Create a directed edge between two nodes."""
    svc = WorkGraphService(session=session)
    edge = svc.link_nodes(
        workspace_id=workspace_id, source_type=source_type, source_id=source_id,
        target_type=target_type, target_id=target_id,
        relationship=relationship, weight=weight,
    )
    return {
        "id": edge.id,
        "relationship_type": edge.relationship_type,
        "source": f"{edge.source_type}:{edge.source_id}",
        "target": f"{edge.target_type}:{edge.target_id}",
    }


@router.get("/graph/related")
def get_related(
    workspace_id: str,
    entity_type: str,
    entity_id: str,
    max_depth: int = Query(3, ge=1, le=10),
    _perm: None = require_permission("graph.read", "*", "graph"),
    session=Depends(get_db_session),
):
    """Traverse the graph from a starting entity using BFS."""
    svc = WorkGraphService(session=session)
    return svc.get_related(
        workspace_id=workspace_id, entity_type=entity_type,
        entity_id=entity_id, max_depth=max_depth,
    )


@router.get("/graph/path")
def find_path(
    workspace_id: str,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    max_depth: int = Query(5, ge=1, le=10),
    _perm: None = require_permission("graph.read", "*", "graph"),
    session=Depends(get_db_session),
):
    """Find the shortest path between two entities."""
    svc = WorkGraphService(session=session)
    result = svc.find_path(
        workspace_id=workspace_id, source_type=source_type, source_id=source_id,
        target_type=target_type, target_id=target_id, max_depth=max_depth,
    )
    if result is None:
        return {"found": False, "path": [], "hops": 0, "nodes": []}
    return {"found": True, **result}


@router.get("/graph/impact")
def analyze_impact(
    workspace_id: str,
    entity_type: str,
    entity_id: str,
    max_depth: int = Query(3, ge=1, le=10),
    _perm: None = require_permission("graph.read", "*", "graph"),
    session=Depends(get_db_session),
):
    """Analyze the impact of changing an entity."""
    svc = WorkGraphService(session=session)
    return svc.analyze_impact(
        workspace_id=workspace_id, entity_type=entity_type,
        entity_id=entity_id, max_depth=max_depth,
    )


@router.get("/graph/cycle-check")
def check_cycle(
    workspace_id: str,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    _perm: None = require_permission("graph.read", "*", "graph"),
    session=Depends(get_db_session),
):
    """Check if adding an edge would create a cycle."""
    svc = WorkGraphService(session=session)
    would = svc.would_create_cycle(
        workspace_id=workspace_id, source_type=source_type, source_id=source_id,
        target_type=target_type, target_id=target_id,
    )
    return {"would_create_cycle": would}


@router.post("/graph/snapshots")
def create_snapshot(
    workspace_id: str,
    entity_type: str,
    entity_id: str,
    depth: int = 2,
    name: Optional[str] = None,
    _perm: None = require_permission("graph.create", "*", "graph"),
    session=Depends(get_db_session),
):
    """Create a point-in-time snapshot of a subgraph."""
    svc = WorkGraphService(session=session)
    snap = svc.snapshot_subgraph(
        workspace_id=workspace_id, root_entity_type=entity_type,
        root_entity_id=entity_id, depth=depth, name=name,
    )
    return {"id": snap.id, "name": snap.name, "summary": snap.summary}


@router.get("/graph/snapshots")
def list_snapshots(
    workspace_id: str,
    entity_type: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    _perm: None = require_permission("graph.read", "*", "graph"),
    session=Depends(get_db_session),
):
    """List graph snapshots for a workspace."""
    svc = WorkGraphService(session=session)
    snaps = svc.list_snapshots(
        workspace_id=workspace_id, root_entity_type=entity_type, limit=limit,
    )
    return {"snapshots": [s.model_dump() for s in snaps], "total": len(snaps)}


@router.get("/graph/stats")
def get_graph_stats(
    workspace_id: str,
    _perm: None = require_permission("graph.read", "*", "graph"),
    session=Depends(get_db_session),
):
    """Get aggregate graph statistics."""
    svc = WorkGraphService(session=session)
    return svc.get_graph_stats(workspace_id=workspace_id)
