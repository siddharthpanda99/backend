from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException, Body
from pathlib import Path
import yaml
from app.modules.common.types.index import APIResponse

router = APIRouter()

from common_lib.modules.agents.registry import templates_registry_service

@router.get("/", response_model=APIResponse[Dict[str, List[Dict[str, Any]]]])
def list_templates(category: Optional[str] = Query(None, description="Filter by logical category: instructions, guardrails, agents, tools, etc.")):
    """
    List all available templates from the common_lib registry.
    Supports filtering by logical category.
    """
    try:
        results = templates_registry_service.list_templates(category)
        return APIResponse(data=results, message="Templates retrieved successfully")
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}", response_model=APIResponse[Dict[str, Any]])
def get_template(template_id: str):
    """
    Retrieve a specific template by its ID across all categories.
    """
    try:
        data = templates_registry_service.get_template(template_id)
        return APIResponse(data=data, message="Template retrieved successfully")
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/save", response_model=APIResponse[Dict[str, Any]])
def save_template(
    payload: Dict[str, Any] = Body(...),
    category: str = Query(..., description="Logical category: instructions, guardrails, etc.")
):
    """
    Save a new template or update an existing one in the registry.
    """
    try:
        saved = templates_registry_service.save_template(payload, category)
        return APIResponse(data=saved, message=f"Template saved successfully")
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

