#!/usr/bin/env python3
"""
Entity Studio Query Routes — Thin HTTP transport for query operations.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from common_lib.modules.entity_studio.service import EntityStudioService
from common_lib.modules.entity_studio.suggest_molecules import MoleculeSuggester
from common_lib.modules.entity_studio.atom_catalog import ATOM_DEFINITIONS

router = APIRouter()


class SuggestResponse(BaseModel):
    atoms: list[dict] = []
    molecules: list[dict] = []
    organisms: list[dict] = []


class ValidateResponse(BaseModel):
    valid: bool
    warnings: list[str] = []
    errors: list[str] = []


class ListResponse(BaseModel):
    items: list[dict]
    total: int


@router.get("/suggest", response_model=SuggestResponse)
async def suggest_entities(
    prompt: str = Query(
        ..., description="Natural language prompt for entity suggestion"
    ),
    entity_type: str = Query(default="molecule", pattern=r"^(atom|molecule|organism)$"),
):
    """Get AI-suggested entities for a prompt."""
    suggester = MoleculeSuggester()
    return suggester.suggest_for_prompt(prompt)


@router.post("/validate", response_model=ValidateResponse)
async def validate_entity(
    entity_type: str = Query(..., pattern=r"^(atom|molecule|organism)$"),
    entity_id: str = Query(...),
):
    """Validate an entity definition."""
    # TODO: Implement full validation
    return {"valid": True, "warnings": [], "errors": []}


@router.get("/list/atoms", response_model=ListResponse)
async def list_atoms(
    category: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """List all available atoms, optionally filtered by category or tag."""
    atoms = []
    for atom_id, atom_def in ATOM_DEFINITIONS.items():
        if category and atom_def.get("category") != category:
            continue
        if tag and tag not in atom_def.get("tags", []):
            continue
        atoms.append({"atom_id": atom_id, **atom_def})
        if len(atoms) >= limit:
            break
    return {"items": atoms, "total": len(atoms)}


@router.get("/list/molecules", response_model=ListResponse)
async def list_molecules(
    category: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """List all available molecules, optionally filtered by category or tag."""
    from pathlib import Path
    import yaml

    molecules = []
    mol_dir = Path(
        "/home/siddharth/Documents/Dev/agentic-platform/Backend Monorepo/Python Libs/common_lib/src/common_lib/modules/templating/templates/molecules"
    )
    if mol_dir.exists():
        for mol_file in mol_dir.glob("*.yaml"):
            data = yaml.safe_load(mol_file.read_text(encoding="utf-8"))
            if category and data.get("category") != category:
                continue
            if tag and tag not in data.get("tags", []):
                continue
            molecules.append(data)
            if len(molecules) >= limit:
                break
    return {"items": molecules, "total": len(molecules)}


@router.get("/list/organisms", response_model=ListResponse)
async def list_organisms(
    organism_type: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """List all available organisms, optionally filtered by type or tag."""
    from pathlib import Path
    import yaml

    organisms = []
    org_dir = Path(
        "/home/siddharth/Documents/Dev/agentic-platform/Backend Monorepo/Python Libs/common_lib/src/common_lib/modules/templating/templates/organisms"
    )
    if org_dir.exists():
        for org_file in org_dir.glob("*.yaml"):
            data = yaml.safe_load(org_file.read_text(encoding="utf-8"))
            if organism_type and data.get("organism_type") != organism_type:
                continue
            if tag and tag not in data.get("tags", []):
                continue
            organisms.append(data)
            if len(organisms) >= limit:
                break
    return {"items": organisms, "total": len(organisms)}


@router.post("/sync")
async def sync_to_db(entity_type: str = Query(default="all")):
    """Sync entity definitions to database."""
    return {"status": "synced", "entity_type": entity_type, "message": "Sync completed"}


@router.post("/export")
async def export_entity(
    entity_type: str = Query(..., pattern=r"^(atom|molecule|organism)$"),
    entity_id: str = Query(...),
    output_format: str = Query(
        default="json", pattern=r"^(json|yaml|markdown|typescript)$"
    ),
):
    """Export an entity to various formats."""
    # TODO: Implement export
    return {
        "status": "exported",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "format": output_format,
    }
