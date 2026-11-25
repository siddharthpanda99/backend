#!/usr/bin/env python3
"""
Entity Studio Atom Routes — Thin HTTP transport for atom operations.
"""

from fastapi import APIRouter, HTTPException, Query
from common_lib.modules.entity_studio.service import EntityStudioService
from common_lib.modules.entity_studio.schemas import (
    AtomCreateRequest,
    EntityCreateResponse,
    AtomQueryParams,
)

router = APIRouter()


@router.post("", response_model=EntityCreateResponse)
async def create_atom(
    request: AtomCreateRequest,
    actor: str = Query(default="system", description="Actor creating the atom"),
):
    """Create a new atom definition."""
    service = EntityStudioService()
    result = await service.create_atom(
        atom_id=request.atom_id,
        name=request.name,
        category=request.category,
        content=request.content,
        description=request.description,
        format=request.format,
        variables=request.variables,
        dependencies=request.dependencies,
        tags=request.tags,
        use_cases=request.use_cases,
        platforms=request.platforms,
        ai_instructions=request.ai_instructions,
        ai_warnings=request.ai_warnings,
        ai_context=request.ai_context,
        ai_prerequisites=request.ai_prerequisites,
        human_instructions=request.human_instructions,
        human_warnings=request.human_warnings,
        human_notes=request.human_notes,
        examples=request.examples,
        anti_patterns=request.anti_patterns,
        related_atoms=request.related_atoms,
        owner=request.owner,
        maintainers=request.maintainers,
        reviewers=request.reviewers,
        approval_status=request.approval_status,
        version=request.version,
        is_system=request.is_system,
        deprecated=request.deprecated,
        deprecated_reason=request.deprecated_reason,
        superseded_by=request.superseded_by,
        metadata=request.metadata,
        actor=actor,
    )
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["message"])
    return result


@router.get("/{atom_id}")
async def get_atom(atom_id: str):
    """Get atom by ID."""
    service = EntityStudioService()
    result = await service.get_atom(atom_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Atom {atom_id} not found")
    return result
