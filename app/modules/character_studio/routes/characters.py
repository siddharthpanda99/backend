"""Character CRUD routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from common_lib.modules.common.feature_flags import is_enabled
from app.modules.character_studio.routes.models import (
    CharacterCreateBody,
    CharacterPatchBody,
    CharacterRead,
    ListResponse,
)

router = APIRouter()

API = "/api/v1/character-studio"


def _guard() -> None:
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        raise HTTPException(status_code=403, detail="character_studio module disabled")


def _call(fn_name: str, *args: Any, **kwargs: Any) -> Any:
    from common_lib.modules.image_processing.character_studio.operations import (
        create_character,
        list_characters,
        get_character,
        update_character,
    )

    return getattr(
        __import__(
            "common_lib.modules.image_processing.character_studio.operations",
            fromlist=[""],
        ),
        fn_name,
    )(*args, **kwargs)


def _non_none(**kwargs: Any) -> Dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


@router.post(
    "/characters",
    response_model=CharacterRead,
    status_code=201,
)
async def create_character(body: CharacterCreateBody) -> CharacterRead:
    """Create a new character entry."""
    from app.modules.character_studio.routes.models import CharacterCreateBody

    return _call(
        "create_character",
        character_id=body.character_id,
        name=body.name,
        description=body.description,
    )


@router.get("/characters", response_model=ListResponse[CharacterRead])
async def list_characters() -> ListResponse[CharacterRead]:
    """List all Character Studio characters."""
    items, total = _call("list_characters")
    return ListResponse[CharacterRead](items=list(items), total=total)


@router.get("/characters/{character_id}", response_model=CharacterRead)
async def get_character(character_id: str) -> CharacterRead:
    """Get a character by ID."""
    return _call("get_character", character_id)


@router.patch("/characters/{character_id}", response_model=CharacterRead)
async def patch_character(character_id: str, body: CharacterPatchBody) -> CharacterRead:
    """Update a character (name/description/status)."""
    return _call(
        "update_character",
        character_id,
        **_non_none(name=body.name, description=body.description, status=body.status),
    )
