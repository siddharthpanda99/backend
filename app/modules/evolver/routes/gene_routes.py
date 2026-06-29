"""Evolver Gene routes — CRUD for behavioral gene definitions."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from app.modules.common.types.index import APIResponse

router = APIRouter(prefix="/genes", tags=["Evolver Genes"])


class GeneCreateRequest(BaseModel):
    gene_id: str
    name: str
    description: str = ""
    trigger_pattern: str = ""
    min_repetitions: int = 0
    max_uses: int = 10
    effect_type: str = "system_prompt_append"
    effect_content: str = ""
    is_active: bool = True


class GeneUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_pattern: Optional[str] = None
    min_repetitions: Optional[int] = None
    max_uses: Optional[int] = None
    effect_type: Optional[str] = None
    effect_content: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("", response_model=APIResponse[List[Dict[str, Any]]])
async def list_genes(active_only: bool = False, limit: int = 100, offset: int = 0):
    """List all gene definitions."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
            GeneRecordService,
        )

        svc = GeneRecordService()
        genes = svc.list_all(active_only=active_only, limit=limit, offset=offset)
        return APIResponse(
            data=[g.model_dump() for g in genes], message="Genes retrieved"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{gene_id}", response_model=APIResponse[Dict[str, Any]])
async def get_gene(gene_id: str):
    """Get a specific gene by gene_id."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
            GeneRecordService,
        )

        svc = GeneRecordService()
        gene = svc.get_by_gene_id(gene_id)
        if not gene:
            raise HTTPException(status_code=404, detail=f"Gene {gene_id} not found")
        return APIResponse(data=gene.model_dump(), message="Gene retrieved")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=APIResponse[Dict[str, Any]])
async def create_gene(req: GeneCreateRequest):
    """Create a new gene definition."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
            GeneRecordService,
        )

        svc = GeneRecordService()
        gene = svc.create(
            gene_id=req.gene_id,
            name=req.name,
            description=req.description,
            trigger_pattern=req.trigger_pattern,
            min_repetitions=req.min_repetitions,
            max_uses=req.max_uses,
            effect_type=req.effect_type,
            effect_content=req.effect_content,
            is_active=req.is_active,
        )
        return APIResponse(data=gene.model_dump(), message="Gene created")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{gene_id}", response_model=APIResponse[Dict[str, Any]])
async def update_gene(gene_id: str, req: GeneUpdateRequest):
    """Update a gene definition."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
            GeneRecordService,
        )

        svc = GeneRecordService()
        record = svc.get_by_gene_id(gene_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Gene {gene_id} not found")
        updates = {k: v for k, v in req.model_dump(exclude_none=True).items()}
        updated = svc.update(record.id, **updates)
        return APIResponse(data=updated.model_dump(), message="Gene updated")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{gene_id}", response_model=APIResponse)
async def delete_gene(gene_id: str):
    """Delete a gene definition."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
            GeneRecordService,
        )

        svc = GeneRecordService()
        record = svc.get_by_gene_id(gene_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Gene {gene_id} not found")
        svc.delete(record.id)
        return APIResponse(data=None, message="Gene deleted")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
