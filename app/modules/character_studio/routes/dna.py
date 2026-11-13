"""DNA routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from common_lib.modules.common.feature_flags import is_enabled
from app.modules.character_studio.routes.models import (
    DNARead,
    DNACreateBody,
    DNAUpdateBody,
    DNAUpsertBody,
)

router = APIRouter()

API = "/api/v1/character-studio"


def _guard() -> None:
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        raise HTTPException(status_code=403, detail="character_studio module disabled")


def _call(fn_name: str, *args: Any, **kwargs: Any) -> Any:
    from common_lib.modules.image_processing.character_studio.operations import (
        get_dna,
        upsert_dna,
    )

    return getattr(
        __import__(
            "common_lib.modules.image_processing.character_studio.operations",
            fromlist=[""],
        ),
        fn_name,
    )(*args, **kwargs)


@router.get("/characters/{character_id}/dna", response_model=DNARead)
async def get_dna(character_id: str) -> DNARead:
    """Get the current DNA for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        get_dna as get_dna_op,
    )
    from common_lib.modules.image_processing.character_studio.exceptions import (
        CharacterStudioError,
    )

    try:
        return get_dna_op(character_id)
    except CharacterStudioError as exc:
        if exc.code == "NOT_FOUND":
            raise HTTPException(status_code=404, detail=exc.message)
        raise


@router.put("/characters/{character_id}/dna", response_model=DNARead)
async def put_dna(character_id: str, body: DNAUpdateBody) -> DNARead:
    """Update the DNA for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        upsert_dna,
    )

    return upsert_dna(character_id, **body.model_dump(exclude_unset=True))


@router.post("/characters/{character_id}/dna", response_model=DNARead)
async def upsert_dna(character_id: str, body: DNAUpsertBody) -> DNARead:
    """Create or replace the DNA for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        upsert_dna,
    )

    return upsert_dna(character_id, **body.model_dump(exclude_unset=True))
