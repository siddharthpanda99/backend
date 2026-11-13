"""Job routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from common_lib.modules.common.feature_flags import is_enabled
from app.modules.character_studio.routes.models import (
    JobRead,
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
        get_job,
        list_jobs,
        cancel_job,
    )

    return getattr(
        __import__(
            "common_lib.modules.image_processing.character_studio.operations",
            fromlist=[""],
        ),
        fn_name,
    )(*args, **kwargs)


@router.get("/generation-jobs/{job_id}", response_model=JobRead)
async def get_job(job_id: UUID) -> JobRead:
    """Get a generation job by ID."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import get_job

    return get_job(job_id)


@router.get(
    "/characters/{character_id}/generation-jobs", response_model=ListResponse[JobRead]
)
async def list_jobs(character_id: Optional[str] = None) -> ListResponse[JobRead]:
    """List generation jobs for a character."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        list_jobs,
    )

    rows = list_jobs(character_id)
    return ListResponse[JobRead](items=list(rows), total=len(rows))


@router.post("/generation-jobs/{job_id}/cancel", response_model=JobRead)
async def cancel_job(job_id: UUID) -> JobRead:
    """Cancel a queued/running generation job."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        cancel_job,
    )

    return cancel_job(job_id)


@router.get("/generation-jobs", response_model=ListResponse[JobRead])
async def list_generation_jobs(
    character_id: Optional[str] = None,
) -> ListResponse[JobRead]:
    """List generation jobs."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        list_jobs,
    )

    rows = list_jobs(character_id)
    return ListResponse[JobRead](items=list(rows), total=len(rows))
