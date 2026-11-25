#!/usr/bin/env python3
"""
Entity Studio Molecule Routes — Thin HTTP transport for molecule operations.
"""

from fastapi import APIRouter, HTTPException, Query
from common_lib.modules.entity_studio.service import EntityStudioService
from common_lib.modules.entity_studio.schemas import (
    MoleculeCreateRequest,
    EntityCreateResponse,
)

router = APIRouter()


@router.post("", response_model=EntityCreateResponse)
async def create_molecule(
    request: MoleculeCreateRequest,
    actor: str = Query(default="system", description="Actor creating the molecule"),
):
    """Create a new molecule definition."""
    service = EntityStudioService()
    result = await service.create_molecule(
        molecule_id=request.molecule_id,
        name=request.name,
        description=request.description,
        category=request.category,
        atom_ids=request.atom_ids,
        priority=request.priority,
        is_system=request.is_system,
        tags=request.tags,
        atom_categories=request.atom_categories,
        config_schema=request.config_schema,
        default_values=request.default_values,
        actor=actor,
    )
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["message"])
    return result


@router.get("/{molecule_id}")
async def get_molecule(molecule_id: str):
    """Get molecule by ID."""
    service = EntityStudioService()
    result = await service.get_molecule(molecule_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Molecule {molecule_id} not found")
    return result
