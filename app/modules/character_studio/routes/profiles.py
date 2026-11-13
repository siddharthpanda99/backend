"""Profile routes - generation profiles and style profiles."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from common_lib.modules.common.feature_flags import is_enabled
from app.modules.character_studio.routes.models import (
    GenerationProfileCreateBody,
    GenerationProfileRead,
    StyleProfileCreateBody,
    StyleProfileRead,
    ListResponse,
    GenerationProfileCreateBody,
    GenerationProfileRead,
    StyleProfileCreateBody,
    StyleProfileRead,
    OutfitCreateBody,
    OutfitRead,
    GenerationProfileCreateBody,
    GenerationProfileRead,
    StyleProfileCreateBody,
    StyleProfileRead,
)

router = APIRouter()

API = "/api/v1/character-studio"


def _guard() -> None:
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        raise HTTPException(status_code=403, detail="character_studio module disabled")


def _call(fn_name: str, *args: Any, **kwargs: Any) -> Any:
    from common_lib.modules.image_processing.character_studio.operations import (
        create_generation_profile,
        list_generation_profiles,
        get_generation_profile,
        update_generation_profile,
        delete_generation_profile,
        create_style_profile,
        list_style_profiles,
        get_style_profile,
        update_style_profile,
        delete_style_profile,
        create_outfit,
        list_outfits,
        get_outfit,
        update_outfit,
        delete_outfit,
        create_accessory,
        list_accessories,
        create_pose,
        list_poses,
        create_expression,
        list_expressions,
    )

    return getattr(
        __import__(
            "common_lib.modules.image_processing.character_studio.operations",
            fromlist=[""],
        ),
        fn_name,
    )(*args, **kwargs)


# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Generation profiles
# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════


@router.post(
    "/characters/{character_id}/profiles/generation",
    response_model=GenerationProfileRead,
    status_code=201,
)
async def create_generation_profile(
    character_id: str, body: GenerationProfileCreateBody
) -> GenerationProfileRead:
    """Create a generation profile for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        create_generation_profile,
    )

    return create_generation_profile(
        character_id, **body.model_dump(exclude_unset=True)
    )


@router.get(
    "/characters/{character_id}/profiles/generation",
    response_model=ListResponse[GenerationProfileRead],
)
async def list_generation_profiles(
    character_id: str,
) -> ListResponse[GenerationProfileRead]:
    """List generation profiles for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        list_generation_profiles,
    )

    items = list_generation_profiles(character_id)
    return ListResponse[GenerationProfileRead](items=list(items), total=len(items))


@router.get(
    "/characters/{character_id}/profiles/generation/{profile_id}",
    response_model=GenerationProfileRead,
)
async def get_generation_profile(
    character_id: str, profile_id: UUID
) -> GenerationProfileRead:
    """Get a generation profile by ID."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        get_generation_profile,
    )

    return get_generation_profile(character_id, profile_id=profile_id)


@router.put(
    "/characters/{character_id}/profiles/generation/{profile_id}",
    response_model=GenerationProfileRead,
)
async def update_generation_profile(
    character_id: str, profile_id: UUID, body: GenerationProfileCreateBody
) -> GenerationProfileRead:
    """Update a generation profile."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        update_generation_profile,
    )

    return update_generation_profile(
        character_id, profile_id=profile_id, **body.model_dump(exclude_unset=True)
    )


@router.delete(
    "/characters/{character_id}/profiles/generation/{profile_id}", status_code=204
)
async def delete_generation_profile(character_id: str, profile_id: UUID):
    """Delete a generation profile."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        delete_generation_profile,
    )

    delete_generation_profile(character_id, profile_id=profile_id)


# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Style profiles
# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════


@router.post(
    "/characters/{character_id}/profiles/style",
    response_model=StyleProfileRead,
    status_code=201,
)
async def create_style_profile(
    character_id: str, body: StyleProfileCreateBody
) -> StyleProfileRead:
    """Create a style profile for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        create_style_profile,
    )

    return create_style_profile(character_id, **body.model_dump(exclude_unset=True))


@router.get(
    "/characters/{character_id}/profiles/style",
    response_model=ListResponse[StyleProfileRead],
)
async def list_style_profiles(character_id: str) -> ListResponse[StyleProfileRead]:
    """List style profiles for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        list_style_profiles,
    )

    items = list_style_profiles(character_id)
    return ListResponse[StyleProfileRead](items=list(items), total=len(items))


@router.get(
    "/characters/{character_id}/profiles/style/{profile_id}",
    response_model=StyleProfileRead,
)
async def get_style_profile(character_id: str, profile_id: UUID) -> StyleProfileRead:
    """Get a style profile by ID."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        get_style_profile,
    )

    return get_style_profile(character_id, profile_id=profile_id)


@router.put(
    "/characters/{character_id}/profiles/style/{profile_id}",
    response_model=StyleProfileRead,
)
async def update_style_profile(
    character_id: str, profile_id: UUID, body: StyleProfileCreateBody
) -> StyleProfileRead:
    """Update a style profile."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        update_style_profile,
    )

    return update_style_profile(
        character_id, profile_id=profile_id, **body.model_dump(exclude_unset=True)
    )


@router.delete(
    "/characters/{character_id}/profiles/style/{profile_id}", status_code=204
)
async def delete_style_profile(character_id: str, profile_id: UUID):
    """Delete a style profile."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        delete_style_profile,
    )

    delete_style_profile(character_id, profile_id=profile_id)


# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Outfits
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════


@router.post(
    "/characters/{character_id}/outfits",
    response_model=OutfitRead,
    status_code=201,
)
async def create_outfit(character_id: str, body: OutfitCreateBody) -> OutfitRead:
    """Create an outfit for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        create_outfit,
    )

    return create_outfit(character_id, **body.model_dump(exclude_unset=True))


@router.get(
    "/characters/{character_id}/outfits", response_model=ListResponse[OutfitRead]
)
async def list_outfits(character_id: str) -> ListResponse[OutfitRead]:
    """List outfits for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        list_outfits,
    )

    items, total = list_outfits(character_id)
    return ListResponse[OutfitRead](items=list(items), total=total)


@router.get("/characters/{character_id}/outfits/{outfit_id}", response_model=OutfitRead)
async def get_outfit(character_id: str, outfit_id: UUID) -> OutfitRead:
    """Get an outfit by ID."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        get_outfit,
    )

    return get_outfit(character_id, outfit_id=outfit_id)


@router.put("/characters/{character_id}/outfits/{outfit_id}", response_model=OutfitRead)
async def update_outfit(
    character_id: str, outfit_id: UUID, body: OutfitCreateBody
) -> OutfitRead:
    """Update an outfit."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        update_outfit,
    )

    return update_outfit(
        character_id, outfit_id=outfit_id, **body.model_dump(exclude_unset=True)
    )


@router.delete("/characters/{character_id}/outfits/{outfit_id}", status_code=204)
async def delete_outfit(character_id: str, outfit_id: UUID):
    """Delete an outfit."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        delete_outfit,
    )

    delete_outfit(character_id, outfit_id=outfit_id)


# ═══════════════════════════════════════════════════════════════════════════
# Accessories
# ═══════════════════════════════════════════════════════════════════════════


from app.modules.character_studio.routes.models import (
    AccessoryCreate,
    AccessoryRead,
    PoseCreate,
    PoseRead,
    ExpressionCreate,
    ExpressionRead,
)


@router.post("/characters/{character_id}/accessories", response_model=AccessoryRead, status_code=201)
async def create_accessory(character_id: str, body: AccessoryCreate) -> AccessoryRead:
    """Create an accessory for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")

    return _call(
        "create_accessory",
        character_id,
        name=body.name,
        category=body.category,
        materials=body.materials,
        colors=body.colors,
        compatible_outfits=body.compatible_outfits,
        asset_id=body.asset_id,
    )


@router.get(
    "/characters/{character_id}/accessories",
    response_model=ListResponse[AccessoryRead],
)
async def list_accessories(character_id: str, category: Optional[str] = None) -> ListResponse[AccessoryRead]:
    """List accessories for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")

    items = _call("list_accessories", character_id, category=category)
    return ListResponse[AccessoryRead](items=[AccessoryRead(**item) for item in items], total=len(items))


# ═══════════════════════════════════════════════════════════════════════════
# Poses
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/characters/{character_id}/poses", response_model=PoseRead, status_code=201)
async def create_pose(character_id: str, body: PoseCreate) -> PoseRead:
    """Create a pose for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")

    return _call(
        "create_pose",
        character_id,
        pose_name=body.pose_name,
        category=body.category,
        front_asset_id=body.front_asset_id,
        side_asset_id=body.side_asset_id,
        back_asset_id=body.back_asset_id,
        openpose_json=body.openpose_json,
        keypoint_confidence=body.keypoint_confidence,
    )


@router.get(
    "/characters/{character_id}/poses",
    response_model=ListResponse[PoseRead],
)
async def list_poses(character_id: str, category: Optional[str] = None) -> ListResponse[PoseRead]:
    """List poses for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")

    items = _call("list_poses", character_id, category=category)
    return ListResponse[PoseRead](items=[PoseRead(**item) for item in items], total=len(items))


# ═══════════════════════════════════════════════════════════════════════════
# Expressions
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/characters/{character_id}/expressions", response_model=ExpressionRead, status_code=201)
async def create_expression(character_id: str, body: ExpressionCreate) -> ExpressionRead:
    """Create an expression for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")

    return _call(
        "create_expression",
        character_id,
        expression_name=body.expression_name,
        category=body.category,
        asset_id=body.asset_id,
        fau=body.fau,
    )


@router.get(
    "/characters/{character_id}/expressions",
    response_model=ListResponse[ExpressionRead],
)
async def list_expressions(character_id: str, category: Optional[str] = None) -> ListResponse[ExpressionRead]:
    """List expressions for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")

    items = _call("list_expressions", character_id, category=category)
    return ListResponse[ExpressionRead](items=[ExpressionRead(**item) for item in items], total=len(items))
