"""Export routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from common_lib.modules.common.feature_flags import is_enabled
from app.modules.character_studio.routes.models import (
    ExportBundleRead,
)

router = APIRouter()

API = "/api/v1/character-studio"


def _guard() -> None:
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        raise HTTPException(status_code=403, detail="character_studio module disabled")


def _call(fn_name: str, *args: Any, **kwargs: Any) -> Any:
    from common_lib.modules.image_processing.character_studio.operations import (
        export_rpg,
        export_social,
        export_comic,
        export_turnaround,
        export_pose_sheet,
        export_comic_pages,
        export_social_grid,
        export_social_carousel,
        export_wardrobe,
    )

    return getattr(
        __import__(
            "common_lib.modules.image_processing.character_studio.operations",
            fromlist=[""],
        ),
        fn_name,
    )(*args, **kwargs)


@router.post(
    "/characters/{character_id}/export/rpg",
    response_model=ExportBundleRead,
)
async def export_rpg(character_id: str) -> ExportBundleRead:
    """Export a character bundle for RPG use."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        export_rpg,
    )

    return ExportBundleRead.model_validate(export_rpg(character_id))


@router.post(
    "/characters/{character_id}/export/social",
    response_model=ExportBundleRead,
)
async def export_social(character_id: str) -> ExportBundleRead:
    """Export a character bundle for social use."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        export_social,
    )

    return ExportBundleRead.model_validate(export_social(character_id))


@router.post(
    "/characters/{character_id}/export/comic",
    response_model=ExportBundleRead,
)
async def export_comic(character_id: str) -> ExportBundleRead:
    """Export a character bundle for comic use."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        export_comic,
    )

    return ExportBundleRead.model_validate(export_comic(character_id))


@router.post(
    "/characters/{character_id}/export/turnaround",
    response_model=ExportBundleRead,
)
async def export_turnaround(character_id: str) -> ExportBundleRead:
    """Export a full character turnaround sheet with views, expressions, and detail shots."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        export_turnaround,
    )

    return ExportBundleRead.model_validate(export_turnaround(character_id))


@router.post(
    "/characters/{character_id}/export/pose-sheet",
    response_model=ExportBundleRead,
)
async def export_pose_sheet(character_id: str) -> ExportBundleRead:
    """Export a pose sheet with front, side, and back views."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        export_pose_sheet,
    )

    return ExportBundleRead.model_validate(export_pose_sheet(character_id))


@router.post(
    "/characters/{character_id}/export/comic-pages",
    response_model=ExportBundleRead,
)
async def export_comic_pages(character_id: str) -> ExportBundleRead:
    """Export a multi-page comic layout from character assets."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        export_comic_pages,
    )

    return ExportBundleRead.model_validate(export_comic_pages(character_id))


@router.post(
    "/characters/{character_id}/export/social-grid",
    response_model=ExportBundleRead,
)
async def export_social_grid(character_id: str) -> ExportBundleRead:
    """Export a social media grid (Instagram post format)."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        export_social_grid,
    )

    return ExportBundleRead.model_validate(export_social_grid(character_id))


@router.post(
    "/characters/{character_id}/export/social-carousel",
    response_model=ExportBundleRead,
)
async def export_social_carousel(character_id: str) -> ExportBundleRead:
    """Export an Instagram carousel / social media carousel."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        export_social_carousel,
    )

    return ExportBundleRead.model_validate(export_social_carousel(character_id))


@router.post(
    "/characters/{character_id}/export/wardrobe",
    response_model=ExportBundleRead,
)
async def export_wardrobe(character_id: str) -> ExportBundleRead:
    """Export a wardrobe/costume gallery for the character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        export_wardrobe,
    )

    return ExportBundleRead.model_validate(export_wardrobe(character_id))
