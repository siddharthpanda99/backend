"""Identity version routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from common_lib.modules.common.feature_flags import is_enabled
from app.modules.character_studio.routes.models import (
    IdentityVersionBody,
    IdentityVersionCreateBody,
    IdentityVersionRead,
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
        create_identity_version,
        list_identities,
    )

    return getattr(
        __import__(
            "common_lib.modules.image_processing.character_studio.operations",
            fromlist=[""],
        ),
        fn_name,
    )(*args, **kwargs)


@router.post(
    "/characters/{character_id}/versions",
    response_model=IdentityVersionRead,
)
async def create_identity_version(
    character_id: str, body: IdentityVersionCreateBody
) -> IdentityVersionRead:
    """Create an identity version snapshot for a character."""
    return _call(
        "create_identity_version",
        character_id,
        version=body.version,
        face_profile_id=body.face_profile_id,
        body_profile_id=body.body_profile_id,
        attribute_policies=body.attribute_policies,
        reference_assets=body.reference_assets,
    )


@router.get(
    "/characters/{character_id}/versions",
    response_model=ListResponse[IdentityVersionRead],
)
async def list_identities(character_id: str) -> ListResponse[IdentityVersionRead]:
    """List identity versions for a character."""
    items = _call("list_identities", character_id)
    return ListResponse[IdentityVersionRead](items=list(items), total=len(items))
