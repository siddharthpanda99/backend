"""Character Studio API routes."""

from fastapi import APIRouter

router = APIRouter(prefix="/character-studio", tags=["Character Studio"])


@router.get("/workflows")
async def list_character_studio_workflows():
    """List all Character Studio workflows."""
    workflows = [
        {
            "id": "character_studio_character_creation",
            "name": "Character Creation",
            "description": "Create initial character candidates from text prompts",
        },
        {
            "id": "character_studio_character_generation",
            "name": "Character Generation",
            "description": "Generate new images of an established character with identity preservation",
        },
        {
            "id": "character_studio_character_edit",
            "name": "Character Edit",
            "description": "Edit existing character images (outfit, background, etc.)",
        },
        {
            "id": "character_studio_reference_sheet",
            "name": "Reference Sheet",
            "description": "Generate reference sheets: turnarounds, expressions, details",
        },
        {
            "id": "character_studio_consistency_evaluation",
            "name": "Consistency Evaluation",
            "description": "Evaluate visual consistency using InsightFace comparison",
        },
        {
            "id": "character_studio_style_profile_generation",
            "name": "Style Profile Generation",
            "description": "Generate style profiles from reference images",
        },
        {
            "id": "character_studio_upscale_enhance",
            "name": "Upscale & Enhance",
            "description": "Upscale and enhance character images for final output",
        },
    ]
    return {"workflows": workflows}


@router.get("/data-configs")
async def list_character_studio_data_configs():
    """List all Character Studio data configurations."""
    configs = [
        "character_creation",
        "character_generation",
        "character_edit",
        "reference_sheet",
        "consistency_evaluation",
        "style_profile_generation",
        "upscale_enhance",
    ]
    return {"configs": configs}


@router.get("/health")
async def health_check():
    """Health check for Character Studio."""
    return {"status": "healthy", "module": "character_studio"}
