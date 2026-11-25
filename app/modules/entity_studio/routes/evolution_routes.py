#!/usr/bin/env python3
"""
Entity Studio Evolution Routes — Thin HTTP transport for autonomous evolution.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from common_lib.modules.entity_studio.autonomous_evolution import (
    AutonomousEvolutionOrchestrator,
    EvolutionConfig,
    Gap,
)

router = APIRouter()


class ScanGapsResponse(BaseModel):
    gaps_found: int
    gaps: list[dict]


class TriggerEvolutionRequest(BaseModel):
    gap_type: str = Field(
        ..., pattern=r"^(missing_molecule|missing_atom|missing_organism|coverage_gap)$"
    )
    description: str
    context: dict = Field(default_factory=dict)
    priority: int = Field(default=50, ge=1, le=100)


class TriggerEvolutionResponse(BaseModel):
    task_id: str
    gap_id: str
    status: str
    entities_created: int
    entities: list[dict]
    test_results: dict | None = None
    error: str | None = None
    completed_at: str | None = None


class EvolutionStatusResponse(BaseModel):
    running: bool
    agent_id: str
    active_tasks: int
    completed_tasks: int


@router.get("/scan", response_model=ScanGapsResponse)
async def scan_for_gaps():
    """Scan the entity catalog for gaps."""
    from common_lib.modules.entity_studio.autonomous_evolution import GapDetector

    detector = GapDetector()
    gaps = detector.scan_all_gaps()
    return {
        "gaps_found": len(gaps),
        "gaps": [
            {
                "gap_id": g.gap_id,
                "gap_type": g.gap_type,
                "description": g.description,
                "context": g.context,
                "priority": g.priority,
                "status": g.status,
            }
            for g in gaps[:20]
        ],
    }


@router.post("/trigger", response_model=TriggerEvolutionResponse)
async def trigger_evolution(request: TriggerEvolutionRequest):
    """Manually trigger autonomous evolution for a specific gap."""
    config = EvolutionConfig()
    orchestrator = AutonomousEvolutionOrchestrator(config)

    gap = Gap(
        gap_type=request.gap_type,
        description=request.description,
        context=request.context,
        priority=request.priority,
    )

    task = await orchestrator.trigger_evolution(gap)

    return {
        "task_id": task.task_id,
        "gap_id": task.gap.gap_id,
        "status": task.status,
        "entities_created": len(task.created_entities),
        "entities": task.created_entities,
        "test_results": task.test_results,
        "error": task.error,
        "completed_at": task.completed_at,
    }


@router.get("/status", response_model=EvolutionStatusResponse)
async def get_evolution_status():
    """Get the current status of the autonomous evolution loop."""
    # This would require a persistent orchestrator instance
    return {
        "running": False,
        "agent_id": "unknown",
        "active_tasks": 0,
        "completed_tasks": 0,
    }
