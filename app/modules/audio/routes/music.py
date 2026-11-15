"""Music Studio thin routes — transport ONLY.

Delegates 100% to ``common_lib.modules.audio_processing.pipeline.music_engines``
(capabilities, generation, validation) and to the ``audio_processing``
feature-flag registry. No business logic lives here.

Gated by the ``MUSIC_STUDIO`` flag (env ``AUDIO_FLAG_MUSIC_STUDIO``, default
OFF) — every endpoint returns 503 while the flag is OFF.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.paths import RESOURCES_ROOT

from common_lib.modules.audio_processing.memory.feature_flags import (
    MUSIC_STUDIO,
    is_enabled,
)
from common_lib.modules.audio_processing.pipeline.music_engines import (
    MusicCapabilityError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/music", tags=["Music Studio"])

_MUSIC_DIR = RESOURCES_ROOT / "generated_content" / "music"


def _require_enabled() -> None:
    if not is_enabled(MUSIC_STUDIO):
        raise HTTPException(
            status_code=503,
            detail="music studio is disabled (AUDIO_FLAG_MUSIC_STUDIO is off)",
        )


class MusicGenerateRequest(BaseModel):
    engine_id: str = Field(..., description="Engine id from music_caps.json.")
    lyrics: str = Field(..., min_length=1, description="UTF-8 lyrics (line-separated).")
    style: str = Field("", description="Style/vibe prompt (required for yue2).")
    duration_s: int = Field(30, ge=1, le=600, description="Target duration in seconds.")
    out_path: str | None = Field(None, description="Optional absolute WAV destination.")


@router.get("/engines")
def list_engines() -> dict[str, Any]:
    _require_enabled()
    from common_lib.modules.audio_processing.pipeline.music_engines import (
        list_engines as _list,
        load_music_caps,
    )

    caps = load_music_caps()
    return {"schema_version": caps.get("schema_version", 1), "engines": _list()}


@router.post("/generate")
def generate_song(req: MusicGenerateRequest) -> dict[str, Any]:
    _require_enabled()
    from common_lib.modules.audio_processing.pipeline.music_engines import (
        generate,
        validate_lyrics,
    )

    lint = validate_lyrics(req.lyrics)
    if not lint["ok"]:
        raise HTTPException(
            status_code=400, detail={"message": "lyrics rejected", **lint}
        )

    # Adapter input contract: yue2 takes lyrics as the primary text;
    # ace-step-1.5/diffrhythm2 take the style tags as primary text and the
    # lyrics via params['lyrics'].
    if req.engine_id == "yue2":
        text_primary = req.lyrics
    else:
        text_primary = req.style or "music"
    out = req.out_path or str(
        _MUSIC_DIR / f"song_{req.engine_id}_{int(time.time())}.wav"
    )
    params: dict[str, Any] = {"duration_s": req.duration_s, "lyrics": req.lyrics}
    if req.style:
        params["style"] = req.style

    try:
        return generate(req.engine_id, text_primary, params, out)
    except MusicCapabilityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (
        Exception
    ) as exc:  # adapters raise honestly; surface the class, not a stack trace
        logger.error("music generate failed for %s: %s", req.engine_id, exc)
        raise HTTPException(
            status_code=500, detail=f"{exc.__class__.__name__}: {exc}"
        ) from exc


@router.get("/runs")
def list_runs() -> dict[str, Any]:
    _require_enabled()
    runs: list[dict[str, Any]] = []
    if _MUSIC_DIR.is_dir():
        for wav in sorted(
            _MUSIC_DIR.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:50]:
            runs.append(
                {
                    "name": wav.name,
                    "path": str(wav),
                    "size_bytes": wav.stat().st_size,
                    "mtime": wav.stat().st_mtime,
                }
            )
    return {"dir": str(_MUSIC_DIR), "runs": runs}
