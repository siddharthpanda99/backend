#!/usr/bin/env python3
"""
Entity Studio Organism Routes — Thin HTTP transport for organism operations.
"""

from fastapi import APIRouter, HTTPException, Query
from common_lib.modules.entity_studio.service import EntityStudioService
from common_lib.modules.entity_studio.schemas import (
    OrganismCreateRequest,
    EntityCreateResponse,
)

router = APIRouter()


@router.post("", response_model=EntityCreateResponse)
async def create_organism(
    request: OrganismCreateRequest,
    actor: str = Query(default="system", description="Actor creating the organism"),
):
    """Create a new organism (agent/workflow/skill/guardrail/trigger/ruleset)."""
    service = EntityStudioService()
    result = await service.create_organism(
        organism_id=request.organism_id,
        name=request.name,
        description=request.description,
        organism_type=request.organism_type,
        molecule_ids=request.molecule_ids,
        molecule_configs=request.molecule_configs,
        tags=request.tags,
        output_format=request.output_format,
        actor=actor,
    )
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["message"])
    return result


@router.get("/{organism_id}")
async def get_organism(organism_id: str):
    """Get organism by ID."""
    service = EntityStudioService()
    result = await service.get_organism(organism_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Organism {organism_id} not found")
    return result
