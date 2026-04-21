import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Graph"])

GRAPH_NAME = "super_graph"


class GraphNode(BaseModel):
    id: str
    label: str
    category: str
    description: Optional[str] = None
    doc: Optional[str] = None
    tags: List[str] = []
    entity_type: str = "doc"


class GraphEdge(BaseModel):
    from_id: str
    to_id: str
    label: str


class GraphResponse(BaseModel):
    graph: Dict[str, Any]
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    categories: List[str]
    summary: Dict[str, int]


def _get_engine():
    from app.modules.database.service.connection import engine

    return engine


@router.get("/", response_model=GraphResponse)
async def get_graph(refresh: bool = Query(False)):
    """
    Get the full AGE graph with nodes and edges.
    Cache can be bypassed with refresh=true.
    """
    return await _load_graph(refresh)


async def _load_graph(refresh: bool = False) -> GraphResponse:
    """Load graph from AGE."""
    from sqlalchemy import text

    engine = _get_engine()
    nodes = []
    edges = []
    categories = set()
    all_tags: Dict[str, List[str]] = {}

    category_colors = {
        "Core": "#6366f1",
        "Evolution": "#8b5cf6",
        "Features": "#f59e0b",
        "Walkthroughs": "#10b981",
        "Vision": "#f97316",
        "Engine": "#ec4899",
        "Agent": "#a855f7",
        "Workflow": "#22c55e",
        "Procedure": "#3b82f6",
        "Memory": "#06b6d4",
        "Tag": "#94a3b8",
        "Knowledge": "#14b8a6",
        "Section": "#f43f5e",
    }

    with engine.connect() as conn:
        conn.execute(text("LOAD 'age';"))
        conn.execute(text('SET search_path = ag_catalog, "$user", public;'))

        node_query = f"""
        SELECT * FROM cypher('{GRAPH_NAME}', $q$
            MATCH (n) RETURN n
        $q$) as (n agtype);
        """
        try:
            query_result = conn.execute(text(node_query))
        except Exception as e:
            logger.warning(f"Graph query failed: {e}")
            return GraphResponse(
                graph={"id": GRAPH_NAME, "name": "Super Graph"},
                nodes=[],
                edges=[],
                categories=[],
                summary={"nodes": 0, "edges": 0},
            )

        for row in query_result:
            node_raw = row[0]
            node_data = {}

            if isinstance(node_raw, str):
                clean_json = node_raw.split("::")[0] if "::" in node_raw else node_raw
                try:
                    node_data = json.loads(clean_json)
                except:
                    logger.error(f"Failed to parse AGE node: {node_raw}")
                    continue
            elif isinstance(node_raw, dict):
                node_data = node_raw
            else:
                node_data = getattr(node_raw, "__dict__", {})

            props = node_data.get("properties", {})
            node_id = str(props.get("id") or str(node_data.get("id", "")))

            if not node_id or node_id == "None":
                continue

            cat = str(
                props.get("category") or props.get("type") or "Knowledge"
            ).capitalize()
            categories.add(cat)
            node_tags = [str(t) for t in props.get("tags", [])]

            nodes.append(
                GraphNode(
                    id=node_id,
                    label=str(props.get("name") or props.get("filename") or node_id),
                    category=cat,
                    description=str(
                        props.get("description") or props.get("filename") or ""
                    ),
                    doc=props.get("filename") if props.get("filename") else None,
                    tags=node_tags,
                    entity_type=str(props.get("type", "doc")),
                )
            )
            if node_tags:
                all_tags[node_id] = node_tags

        edge_query = f"""
        SELECT * FROM cypher('{GRAPH_NAME}', $q$
            MATCH (a)-[r]->(b)
            WHERE a.id IS NOT NULL AND b.id IS NOT NULL
            RETURN a.id, b.id, label(r)
        $q$) as (a_id agtype, b_id agtype, rel_label agtype);
        """
        try:
            edges_result = conn.execute(text(edge_query))
            for row in edges_result:
                from_id = (
                    str(row[0]).split("::")[0].strip('"')
                    if row[0] is not None
                    else None
                )
                to_id = (
                    str(row[1]).split("::")[0].strip('"')
                    if row[1] is not None
                    else None
                )
                label = (
                    str(row[2]).split("::")[0].strip('"')
                    if row[2] is not None
                    else "RELATED"
                )

                if from_id and to_id:
                    edges.append(GraphEdge(from_id=from_id, to_id=to_id, label=label))
        except Exception as e:
            logger.warning(f"Edge query failed: {e}")

    category_list = sorted(categories)
    for cat in category_list:
        if cat not in category_colors:
            category_colors[cat] = "#64748b"

    graph_data = {
        "id": GRAPH_NAME,
        "name": "Super Graph",
        "version": "2.0.0",
    }

    return GraphResponse(
        graph=graph_data,
        nodes=nodes,
        edges=edges,
        categories=category_list,
        summary={"nodes": len(nodes), "edges": len(edges)},
    )


@router.get("/nodes", response_model=Dict[str, Any])
async def get_graph_nodes():
    """Get all nodes with categories."""
    graph = await _load_graph()
    return {
        "nodes": [n.model_dump() for n in graph.nodes],
        "categories": graph.categories,
    }


@router.get("/node/{node_id}", response_model=GraphNode)
async def get_graph_node(node_id: str):
    """Get a specific node by ID."""
    graph = await _load_graph()
    for node in graph.nodes:
        if node.id == node_id:
            return node
    raise HTTPException(status_code=404, detail=f"Node {node_id} not found")


@router.get("/edges", response_model=List[GraphEdge])
async def get_graph_edges():
    """Get all edges."""
    graph = await _load_graph()
    return graph.edges


@router.get("/search", response_model=Dict[str, Any])
async def search_graph(q: str = ""):
    """Search nodes by label or description."""
    graph = await _load_graph()
    query = q.lower()
    results = []
    for node in graph.nodes:
        if (
            query in node.label.lower()
            or query in (node.description or "").lower()
            or any(query in tag.lower() for tag in node.tags)
        ):
            results.append(node.model_dump())
    return {"results": results, "query": q, "count": len(results)}


@router.post("/clear", response_model=Dict[str, str])
async def clear_graph(confirm: bool = Query(False)):
    """
    Clear the AGE graph.
    Requires confirm=true to actually clear.
    """
    if not confirm:
        return {
            "status": "skipped",
            "message": "Set confirm=true to clear the graph",
        }

    from sqlalchemy import text

    engine = _get_engine()
    with engine.connect() as conn:
        try:
            conn.execute(text(f"SELECT drop_graph('{GRAPH_NAME}', true);"))
            conn.commit()
            return {"status": "cleared", "message": f"Graph {GRAPH_NAME} dropped"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to clear graph: {e}")


@router.post("/project", response_model=Dict[str, Any])
async def project_knowledgebase(
    entity_type: str = Query("knowledgebase"),
):
    """
    Project knowledgebase entries to AGE graph.
    Parses markdown headers, tags, and links.
    """
    from common_lib.modules.orchestration.knowledgebase.projection.projector import (
        KnowledgeBaseGraphProjector,
    )

    projector = KnowledgeBaseGraphProjector()

    try:
        projector.project_all()
        graph = await _load_graph(refresh=True)
        return {
            "status": "projected",
            "nodes": graph.summary["nodes"],
            "edges": graph.summary["edges"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Projection failed: {e}")


@router.get("/stats", response_model=Dict[str, Any])
async def get_graph_stats():
    """Get graph statistics."""
    graph = await _load_graph()

    type_counts: Dict[str, int] = {}
    for node in graph.nodes:
        t = node.entity_type
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "total_nodes": graph.summary["nodes"],
        "total_edges": graph.summary["edges"],
        "by_type": type_counts,
        "categories": graph.categories,
    }
