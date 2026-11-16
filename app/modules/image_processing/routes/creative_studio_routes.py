"""
Creative Studio routes for running YAML recipe workflows.

Thin transport layer — delegates to common_lib image_processing.creative_studio service.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
import asyncio
import time
from pathlib import Path

router = APIRouter(prefix="/creative-studio", tags=["Creative Studio"])


# Request/Response Schemas
class RecipeRunRequest(BaseModel):
    recipe_id: str = Field(..., description="Recipe ID to run")
    image: Optional[str] = Field(
        None, description="Input image path (required for img2img/inpaint recipes)"
    )
    overrides: Optional[Dict[str, Any]] = Field(
        None, description="Prompt variables and numeric overrides"
    )
    out_dir: Optional[str] = Field(None, description="Output directory override")
    force: bool = Field(False, description="Overwrite existing outputs")


class RecipeRunResponse(BaseModel):
    ok: bool
    output: Optional[str] = None
    recipe: str
    seed: Optional[int] = None
    engine: Optional[str] = None
    duration_s: float
    prompt: Optional[str] = None
    vlm: Optional[Dict[str, Any]] = None
    manifest: Optional[str] = None
    error: Optional[str] = None
    status: Optional[str] = None
    dropped: List[str] = []


class RecipeListResponse(BaseModel):
    recipes: List[Dict[str, Any]]
    count: int


class SelfTestResponse(BaseModel):
    results: Dict[str, str]
    all_pass: bool


# Output base directory
DEFAULT_OUTPUT_BASE = Path(
    "/home/siddharth/Documents/Dev/agentic-platform/resources/generated_content/creative_outputs"
)
DEFAULT_OUTPUT_BASE.mkdir(parents=True, exist_ok=True)


@router.get("/recipes", response_model=RecipeListResponse)
async def list_recipes(
    domain: Optional[str] = Query(None, description="Filter by domain"),
):
    """List all available Creative Studio recipes."""
    from common_lib.modules.image_processing.creative_studio.registry import (
        get_registry,
    )

    registry = get_registry()
    recipes = registry.list(domain)

    return RecipeListResponse(
        recipes=[r.model_dump(mode="json") for r in recipes], count=len(recipes)
    )


@router.get("/recipes/{recipe_id}")
async def get_recipe(recipe_id: str):
    """Get a specific recipe by ID."""
    from common_lib.modules.image_processing.creative_studio.registry import (
        get_registry,
    )

    registry = get_registry()
    try:
        recipe = registry.get(recipe_id)
        return recipe.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Recipe not found: {str(e)}")


@router.post("/run", response_model=RecipeRunResponse)
async def run_recipe(request: RecipeRunRequest):
    """Run a Creative Studio recipe workflow."""
    from common_lib.modules.image_processing.creative_studio.service import get_service
    from common_lib.modules.image_processing.creative_studio.registry import (
        get_registry,
    )

    registry = get_registry()
    recipe = registry.get(request.recipe_id)

    # Validate engine override
    engine_override = (
        request.overrides.pop("_engine_override", None) if request.overrides else None
    )
    if engine_override:
        recipe = recipe.model_copy(update={"engine": engine_override})

    # Build prompt from recipe template
    prompt = recipe.render_prompt(request.overrides or {})

    # Validate input image if provided
    img_path = Path(request.image) if request.image else None
    if img_path and not img_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Input image not found: {request.image}"
        )

    # Run the recipe
    t0 = time.time()
    try:
        service = get_service()
        result = service.run_recipe(
            request.recipe_id,
            image=request.image,
            overrides=request.overrides,
            out_dir=request.out_dir,
            force=request.force,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Recipe execution failed: {str(e)}"
        )

    duration = time.time() - t0

    if not result.get("ok"):
        return RecipeRunResponse(
            ok=False,
            recipe=request.recipe_id,
            duration_s=round(time.time() - t0, 2),
            error=result.get("error", "Unknown error"),
            status="failed",
        )

    return RecipeRunResponse(
        ok=True,
        output=result.get("output"),
        recipe=request.recipe_id,
        seed=result.get("seed"),
        engine=result.get("engine"),
        duration_s=round(duration, 2),
        prompt=result.get("prompt"),
        vlm=result.get("vlm"),
        manifest=result.get("manifest"),
        status="completed",
    )


@router.post("/self-test", response_model=SelfTestResponse)
async def self_test_preprocessors():
    """Run CPU self-tests for all preprocessors."""
    from common_lib.modules.image_processing.creative_studio.preprocessors import (
        self_test_all,
    )

    results = self_test_all()
    return SelfTestResponse(
        results=results,
        all_pass=all(v == "PASS" for v in results.values()),
    )


@router.get("/catalog")
async def get_catalog():
    """Get the full recipe catalog index."""
    from common_lib.modules.image_processing.creative_studio.catalog import load_catalog

    catalog = load_catalog()
    return catalog
