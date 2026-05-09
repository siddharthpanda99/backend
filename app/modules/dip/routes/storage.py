from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Dict, Any
from common_lib.modules.dip.document_vault import list_documents

router = APIRouter(prefix="/dip/storage", tags=["dip/storage"])

@router.get("/indexes")
async def list_storage_indexes():
    """List available vector and relational indexes."""
    # Mocking index list for now, integrate with VectorStore later
    return {
        "data": [
            {"id": "idx_memories_episodic", "name": "Episodic Vector Index", "type": "vector", "status": "active"},
            {"id": "idx_memories_semantic", "name": "Semantic Knowledge Index", "type": "vector", "status": "active"},
            {"id": "idx_graph_nodes", "name": "Relational Entity Index", "type": "relational", "status": "active"}
        ]
    }

@router.get("/documents")
async def list_storage_documents(limit: int = Query(100)):
    """List documents stored in the cognitive vault."""
    docs = list_documents(limit)
    return {
        "data": docs,
        "count": len(docs)
    }

@router.get("/metrics")
async def get_storage_metrics():
    """Get storage utilization and performance metrics."""
    return {
        "data": {
            "used_bytes": 1024 * 1024 * 45, # 45MB mock
            "total_documents": len(list_documents(1000)),
            "index_health": "optimal",
            "last_sync": "2026-05-09T00:00:00Z"
        }
    }
