"""Memory Semantics API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Body, Query

router = APIRouter(prefix="/semantics", tags=["Memory Semantics"])

logger = logging.getLogger(__name__)

# Import the integration module and submodule enum
from common_lib.modules.memory.integration import MemorySubModule


@router.get("/clusters")
async def cluster(
    agent_id: str = Query("default", description="Agent identifier"),
    algorithm: Optional[str] = Query(None, description="Clustering algorithm"),
):
    try:
        from common_lib.modules.memory.integration import get_memory_integration

        integration = get_memory_integration()
        await integration.initialize()

        # Try to get integrated service (real data) with fallback to standalone
        semantics_service = await integration.get_integrated_service("semantics")
        if semantics_service and hasattr(
            semantics_service, "get_clusters_with_real_data"
        ):
            # Use real data from MemoryService
            clusters = await semantics_service.get_clusters_with_real_data(
                agent_id, algorithm
            )
        else:
            # Fallback to original standalone service
            from common_lib.modules.memory.memory_semantics.service import (
                get_semantics_service,
            )

            svc = get_semantics_service()
            result = await svc.cluster(agent_id=agent_id, algorithm=algorithm)
            clusters = result.get("clusters", [])

        return {
            "agent_id": agent_id,
            "clusters": clusters,
            "algorithm": algorithm or "hdbscan",
            "memory_count": len(clusters),
            "integration_mode": "memory_service" if semantics_service else "standalone",
        }
    except Exception as e:
        logger.error(f"Failed to get clusters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crystallize")
async def crystallize(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.integration import get_memory_integration

        integration = get_memory_integration()
        await integration.initialize()

        # Use integration for crystallization (maintains standalone + real data)
        focus_area = payload.get("focus_area", "general")

        # Fire crystallization event
        await integration.fire_memory_event(
            "crystallize",
            {"focus_area": focus_area, "payload": payload},
            MemorySubModule.SEMANTICS,
        )

        # Get integrated semantics service
        semantics_service = await integration.get_integrated_service("semantics")
        if semantics_service and hasattr(
            semantics_service, "get_clusters_with_real_data"
        ):
            # Use real data path
            result = await semantics_service.get_clusters_with_real_data("default")
            # Extract crystallization-like result from clusters
            crystallized = {
                "focus_area": focus_area,
                "concepts": [
                    {
                        "id": c.get("id", f"concept_{i}"),
                        "name": c.get("label", f"Concept {i}"),
                        "strength": c.get("density", 0.5),
                        "source_count": c.get("count", 1),
                    }
                    for i, c in enumerate(result[:5])  # Top 5 concepts
                ],
                "summary": f"Crystallized {len(result)} concepts from semantic clusters",
            }
        else:
            # Fallback to original standalone service
            from common_lib.modules.memory.memory_semantics.service import (
                get_semantics_service,
            )

            svc = get_semantics_service()
            result = await svc.crystallize(focus_area=focus_area)
            crystallized = {
                "focus_area": focus_area,
                "concepts": [c.model_dump() for c in result.concepts],
                "summary": result.summary,
            }

        return crystallized
    except Exception as e:
        logger.error(f"Failed to crystallize: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topology")
async def get_topology():
    try:
        from common_lib.modules.memory.integration import get_memory_integration

        integration = get_memory_integration()
        await integration.initialize()

        # Get integrated service for topology
        semantics_service = await integration.get_integrated_service(
            MemorySubModule.SEMANTICS
        )
        if semantics_service and hasattr(
            semantics_service, "get_clusters_with_real_data"
        ):
            # Use real data path
            clusters_result = await semantics_service.get_clusters_with_real_data(
                "default"
            )
            # Convert clusters to topology format
            topology = {
                "nodes": [
                    {
                        "id": c.get("id", f"node_{i}"),
                        "name": c.get("label", f"Concept {i}"),
                        "confidence": c.get("density", 0.5),
                        "weight": c.get("count", 1),
                        "source_memory_ids": [],
                    }
                    for i, c in enumerate(clusters_result)
                ],
                "edges": [],
                "timestamp": clusters_result.get("timestamp"),
            }
        else:
            # Fallback to original standalone service
            from common_lib.modules.memory.memory_semantics.service import (
                get_semantics_service,
            )

            svc = get_semantics_service()
            topology = await svc.get_topology()

        return topology
    except Exception as e:
        logger.error(f"Failed to get topology: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/concepts")
async def get_concepts(
    agent_id: str = Query("default", description="Agent identifier"),
):
    try:
        from common_lib.modules.memory.integration import get_memory_integration

        integration = get_memory_integration()
        await integration.initialize()

        # Get integrated service for concepts
        semantics_service = await integration.get_integrated_service(
            MemorySubModule.SEMANTICS
        )
        if semantics_service and hasattr(
            semantics_service, "get_clusters_with_real_data"
        ):
            # Use real data path - extract concepts from topology/clusters
            clusters_result = await semantics_service.get_clusters_with_real_data(
                agent_id
            )
            concepts = [
                {
                    "id": c.get("id", f"concept_{i}"),
                    "name": c.get("label", f"Concept {i}"),
                    "strength": c.get("density", 0.5),
                    "related": [],
                }
                for i, c in enumerate(clusters_result[:10])  # Top 10 concepts
            ]
        else:
            # Fallback to original standalone service
            from common_lib.modules.memory.memory_semantics.service import (
                get_semantics_service,
            )

            svc = get_semantics_service()
            concepts = await svc.get_concepts(agent_id=agent_id)

        return concepts
    except Exception as e:
        logger.error(f"Failed to get concepts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_topology(
    agent_id: str = Body("default", description="Agent identifier"),
):
    try:
        from common_lib.modules.memory.integration import get_memory_integration

        integration = get_memory_integration()
        await integration.initialize()

        # Get integrated service for refresh
        semantics_service = await integration.get_integrated_service(
            MemorySubModule.SEMANTICS
        )
        if semantics_service and hasattr(
            semantics_service, "get_clusters_with_real_data"
        ):
            # Use real data path
            clusters_result = await semantics_service.get_clusters_with_real_data(
                agent_id
            )
            existing = len(clusters_result)
            result = {
                "agent_id": agent_id,
                "refreshed": True,
                "nodes_added": existing,
                "edges_added": 0,  # Simplified for now
            }
        else:
            # Fallback to original standalone service
            from common_lib.modules.memory.memory_semantics.service import (
                get_semantics_service,
            )

            svc = get_semantics_service()
            result = await svc.refresh_topology(agent_id=agent_id)

        return result
    except Exception as e:
        logger.error(f"Failed to refresh topology: {e}")
        raise HTTPException(status_code=500, detail=str(e))
