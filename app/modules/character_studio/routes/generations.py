"""Generation routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from common_lib.modules.common.feature_flags import is_enabled
from app.modules.character_studio.routes.models import (
    GenerationBody,
    GenerationBody,
    VariationsBody,
    ReferenceSheetBody,
    JobRead,
    ListResponse,
    JobRead,
)

router = APIRouter()

API = "/api/v1/character-studio"


def _guard() -> None:
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        raise HTTPException(status_code=403, detail="character_studio module disabled")


def _call(fn_name: str, *args: Any, **kwargs: Any) -> Any:
    from common_lib.modules.image_processing.character_studio.operations import (
        create_generation_job,
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


def _job_kwargs(
    body: "GenerationBody", count: int = 1, intent: Optional[str] = None
) -> Dict[str, Any]:
    return {
        "intent": intent or body.intent,
        "provider": body.provider,
        "style_profile": body.style_profile,
        "checkpoint": body.checkpoint,
        "engine": None,
        "steps": body.steps,
        "cfg": body.cfg,
        "seed": body.seed,
        "policy": body.policy,
        "prompt_override": body.prompt_override,
        "count": count,
    }


def _schedule_generation_job(job: Any) -> None:
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop (non-request context): job stays queued and can be
        # drained by a dedicated worker via run_generation_job.
        return
    job_id = getattr(job, "job_id", job)
    loop.create_task(_run_generation_job_background(job_id))


async def _run_generation_job_background(job_id: Any) -> None:
    """Worker: execute a queued generation job via common_lib."""
    import asyncio
    import logging

    logger = logging.getLogger(__name__)
    try:
        ops = _ops()
        result = await asyncio.to_thread(ops.run_generation_job, job_id)
        logger.info(
            "character_studio generation job %s -> %s",
            job_id,
            getattr(result, "status", None),
        )
    except Exception as exc:  # noqa: BLE001 - common_lib records failure itself
        logger.exception("character_studio generation job %s crashed: %s", job_id, exc)


def _ops():
    from common_lib.modules.image_processing.character_studio.operations import (
        run_generation_job,
    )

    return run_generation_job


def _schedule_generation_job(job: Any) -> None:
    """Enqueue the job for in-process background execution on the live loop."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop (non-request context): job stays queued and can be
        # drained by a dedicated worker via run_generation_job.
        return
    job_id = getattr(job, "job_id", job)
    loop.create_task(_run_generation_job_background(job_id))


def _job_kwargs(
    body: "GenerationBody", count: int = 1, intent: Optional[str] = None
) -> Dict[str, Any]:
    return {
        "intent": intent or body.intent,
        "provider": body.provider,
        "style_profile": body.style_profile,
        "checkpoint": body.checkpoint,
        "engine": None,
        "steps": body.steps,
        "cfg": body.cfg,
        "seed": body.seed,
        "policy": body.policy,
        "prompt_override": body.prompt_override,
        "count": count,
    }


@router.post(
    "/characters/{character_id}/generate",
    response_model=JobRead,
    status_code=202,
)
async def generate(character_id: str, body: GenerationBody) -> JobRead:
    """Queue a generation job for a character."""
    _guard()
    job = _call("create_generation_job", character_id, **_job_kwargs(body))
    _schedule_generation_job(job)
    return job


@router.post(
    "/characters/{character_id}/edit",
    response_model=JobRead,
    status_code=202,
)
async def edit(character_id: str, body: GenerationBody) -> JobRead:
    """Queue an edit job for a character."""
    _guard()
    job = _call("create_generation_job", character_id, **_job_kwargs(body))
    _schedule_generation_job(job)
    return job


@router.post(
    "/characters/{character_id}/variations",
    response_model=JobRead,
    status_code=202,
)
async def variations(character_id: str, body: VariationsBody) -> JobRead:
    """Queue a variations job for a character (1–4 images)."""
    _guard()
    return _call(
        "create_generation_job",
        character_id,
        **_job_kwargs(body, count=body.count),
    )


@router.post(
    "/characters/{character_id}/reference-sheets",
    response_model=JobRead,
    status_code=202,
)
async def reference_sheets(character_id: str, body: ReferenceSheetBody) -> JobRead:
    """Queue a reference-sheet job for a character."""
    _guard()
    intent = "reference_sheet" if body.view == "all" else f"reference_sheet:{body.view}"
    return _call(
        "create_generation_job",
        character_id,
        **_job_kwargs(GenerationBody(intent=intent), count=1, intent=intent),
    )


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
    rows = _call("list_jobs", character_id)
    return ListResponse[JobRead](items=list(rows), total=len(rows))


@router.post("/generation-jobs/{job_id}/cancel", response_model=JobRead)
async def cancel_job(job_id: UUID) -> JobRead:
    """Cancel a queued/running generation job."""
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        raise HTTPException(status_code=403, detail="character_studio module disabled")
    from common_lib.modules.image_processing.character_studio.operations import (
        cancel_job,
    )

    return cancel_job(job_id)
