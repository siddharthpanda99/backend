"""YuE & YuE2 Frontier Music Generation thin routes.

Transport ONLY: delegates every operation to common_lib audio_processing modules
(`YuEGenerator`, `strip_chords`, `validate_abc`, `edit_music`).
Business logic remains strictly in common_lib.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from common_lib.modules.audio_processing.composition.abc_tools import (
    report_abc,
    strip_chords,
)
from common_lib.modules.audio_processing.generation.music.yue import YuEGenerator
from common_lib.modules.audio_processing.schemas.yue import (
    YuECoverRequest,
    YuEEditRequest,
    YuESongRequest,
    YuESongResponse,
    YuESymbolicPlanResponse,
)

from app.modules.audio.runtime.actor import capture_job_actor, owned_job_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yue",
    tags=["YuE Music Generation"],
    dependencies=[Depends(capture_job_actor)],
)


def _ensure_audio_jobs():
    """Register audio executors and return the actor-aware JobService proxy."""
    return owned_job_service()


def _job_payload(record: Any) -> dict[str, Any]:
    refs: list[str] = []
    try:
        refs = [str(r) for r in (record.get_result_refs() or [])]
    except Exception:
        refs = []
    return {
        "job_id": str(record.id),
        "status": str(record.status),
        "kind": str(record.kind),
        "progress": float(record.progress or 0.0),
        "result_refs": refs,
        "error": record.error,
    }


@router.post("/generate")
def generate_song(req: YuESongRequest, sync: bool = False) -> dict[str, Any]:
    """Generate a complete song with vocals and accompaniment from lyrics and style prompt.

    Jobs-backed by default (``audio.yue.generate`` executor, artifacts on
    disk); pass ``sync=true`` to run inline (legacy synchronous response).
    """
    if not sync:
        from app.modules.audio.runtime.job_executors import YUE_GENERATE_KIND

        record = _ensure_audio_jobs().submit(
            YUE_GENERATE_KIND, params=req.model_dump(mode="json")
        )
        return {"status": "queued", **_job_payload(record)}
    try:
        gen = YuEGenerator()
        res = gen.generate(
            style=req.style,
            lyrics=req.lyrics,
            cot=req.cot,
            seed=req.seed,
            abc=req.abc,
            output_path=f"outputs/{req.id}.{req.output_format}",
        )
        return res
    except Exception as exc:
        logger.error("YuE generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/plan")
def plan_song(req: YuESongRequest, sync: bool = False) -> dict[str, Any]:
    """Generate or retrieve a symbolic ABC music plan (melody + chords).

    Jobs-backed by default; pass ``sync=true`` to run inline.
    """
    if not sync:
        from app.modules.audio.runtime.job_executors import YUE_PLAN_KIND

        record = _ensure_audio_jobs().submit(
            YUE_PLAN_KIND, params=req.model_dump(mode="json")
        )
        return {"status": "queued", **_job_payload(record)}
    try:
        gen = YuEGenerator()
        res = gen.plan(
            style=req.style,
            lyrics=req.lyrics,
            cot=req.cot,
            seed=req.seed,
        )
        return res
    except Exception as exc:
        logger.error("YuE planning failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/cover")
def cover_song(req: YuECoverRequest, sync: bool = False) -> dict[str, Any]:
    """Zero-shot cover of an existing audio recording with a target musical style.

    Jobs-backed by default; pass ``sync=true`` to run inline.
    """
    if not sync:
        from app.modules.audio.runtime.job_executors import YUE_COVER_KIND

        record = _ensure_audio_jobs().submit(
            YUE_COVER_KIND, params=req.model_dump(mode="json")
        )
        return {"status": "queued", **_job_payload(record)}
    try:
        gen = YuEGenerator()
        res = gen.cover(
            audio_path=req.audio_path,
            target_style=req.target_style,
            new_lyrics=req.new_lyrics,
            retain_harmony=req.retain_harmony,
            seed=req.seed,
        )
        return res
    except Exception as exc:
        logger.error("YuE cover failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/abc/strip-chords")
def strip_abc_chords(payload: dict[str, str]) -> dict[str, Any]:
    """Strip chord annotations from ABC score while preserving melody and rests."""
    abc = payload.get("abc", "")
    if not abc:
        raise HTTPException(status_code=400, detail="Missing 'abc' score in payload")
    try:
        output = strip_chords(abc, keep_voice=payload.get("keep_voice", "both"))
        return {"ok": True, "abc": output}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/abc/validate")
def validate_abc(payload: dict[str, str]) -> dict[str, Any]:
    """Validate structure and extract note/meter events from native ABC score."""
    abc = payload.get("abc", "")
    if not abc:
        raise HTTPException(status_code=400, detail="Missing 'abc' score in payload")
    try:
        report = report_abc(abc)
        return {"ok": True, "valid": True, "report": report}
    except Exception as exc:
        return {"ok": False, "valid": False, "error": str(exc)}


@router.post("/edit")
def edit_song(req: YuEEditRequest, sync: bool = False) -> dict[str, Any]:
    """Conversational music editing on score and parameters.

    Jobs-backed by default; pass ``sync=true`` to run inline.
    """
    if not sync:
        from app.modules.audio.runtime.job_executors import YUE_EDIT_KIND

        record = _ensure_audio_jobs().submit(
            YUE_EDIT_KIND, params=req.model_dump(mode="json")
        )
        return {"status": "queued", **_job_payload(record)}
    from common_lib.modules.audio_processing.agents.music_editor import edit_music

    if not req.abc:
        raise HTTPException(status_code=400, detail="Missing 'abc' score in request")
    try:
        res = edit_music(
            abc=req.abc,
            instruction=req.instructions,
            target_style=req.target_style,
            new_lyrics=req.new_lyrics,
        )
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
