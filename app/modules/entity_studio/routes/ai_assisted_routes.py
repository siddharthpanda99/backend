#!/usr/bin/env python3
"""
Entity Studio AI-Assisted Routes — Thin HTTP transport for AI-assisted creation.
"""

from fastapi import APIRouter, HTTPException
from common_lib.modules.entity_studio.service import EntityStudioService
from common_lib.modules.entity_studio.schemas import (
    AIAssistedCreateRequest,
    AIAssistedResponse,
)

router = APIRouter()


@router.post("", response_model=AIAssistedResponse)
async def ai_assisted_create(request: AIAssistedCreateRequest):
    """AI-assisted entity creation using Nemotron 3 Ultra (NVIDIA NIM)."""
    service = EntityStudioService()
    result = await service.ai_assisted_create(
        prompt=request.prompt,
        entity_type=request.entity_type,
        target_category=request.target_category,
        context=request.context,
        use_nemotron=request.use_nemotron,
    )
    return result
