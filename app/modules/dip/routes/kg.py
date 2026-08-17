from fastapi import APIRouter, Query, HTTPException, Body
from typing import List, Dict, Any, Optional
import os
from common_lib.modules.knowledge_engine.graph import GraphService
from common_lib.paths import get_repo_root

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

def _resolve_node_path(node_path: str) -> str:
    repo_root = get_repo_root()
    clean_path = node_path
    while clean_path.startswith("../") or clean_path.startswith("..\\"):
        clean_path = clean_path[3:]
        
    monorepo_root = repo_root.parent
    full_path = os.path.join(monorepo_root, clean_path)
    
    if os.path.exists(full_path):
        return full_path
        
    return os.path.join(repo_root, node_path)

@router.get("/entities/{node_id}/content")
async def get_kg_entity_content(node_id: str):
    """Get the full content for a knowledge graph entity."""
    # Try fetching content directly from graph first
    from common_lib.modules.data_storage.database.connection import engine
    from sqlalchemy import text
    import json
    
    with engine.connect() as conn:
        conn.execute(text("LOAD 'age';"))
        conn.execute(text('SET search_path = ag_catalog, "$user", public;'))
        def e(s):
            if s is None: return ""
            return str(s).replace("\\", "\\\\").replace("'", "\\'")
            
        try:
            query = f"""
            SELECT * FROM cypher('super_graph', $q$
                MATCH (d) WHERE d.id = '{e(node_id)}'
                RETURN d.content
            $q$) as (content agtype);
            """
            result = conn.execute(text(query)).scalar()
            if result and result != 'null':
                content_str = json.loads(result)
                if content_str:
                    return {"content": content_str, "path": None}
        except Exception:
            pass

    # Fallback to file reading
    node = await _graph_svc.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
        
    if not getattr(node, "path", None):
        return {"content": None}
        
    full_path = _resolve_node_path(node.path)
    
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return {"content": None}
        
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content, "path": node.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

@router.put("/entities/{node_id}/content")
async def update_kg_entity_content(node_id: str, content: str = Body(..., embed=True)):
    """Update the full content for a knowledge graph entity."""
    node = await _graph_svc.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
        
    # Update Apache AGE first
    from common_lib.modules.data_storage.database.connection import engine
    from sqlalchemy import text
    
    try:
        with engine.connect() as conn:
            conn.execute(text("LOAD 'age';"))
            conn.execute(text('SET search_path = ag_catalog, "$user", public;'))
            
            def e(s):
                if s is None: return ""
                return str(s).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
                
            query = f"""
            SELECT * FROM cypher('super_graph', $q$
                MATCH (d) WHERE d.id = '{e(node_id)}'
                SET d.content = '{e(content)}'
                RETURN d
            $q$) as (d agtype);
            """
            conn.execute(text(query))
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update graph: {str(e)}")
        
    # If it has an associated file, update the file too
    if getattr(node, "path", None):
        full_path = _resolve_node_path(node.path)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            try:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                pass # Just ignore file write errors for now if the graph succeeded
                
    return {"status": "success", "message": "Content updated"}

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
