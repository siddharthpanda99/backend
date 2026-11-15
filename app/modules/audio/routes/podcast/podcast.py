from __future__ import annotations

"""Podcast Studio routes — thin transport layer.

Endpoints:
- POST /podcast/process — process episode (cleanup, loudnorm, etc.)
- POST /podcast/trim-silence — trim silence from audio
- POST /podcast/detect-chapters — detect chapters from silence gaps
- POST /podcast/multi-guest-split — split multi-guest recording
- POST /podcast/generate-show-notes — generate show notes from transcript

All endpoints gated behind LONGFORM_ENABLED flag (default-OFF) since they
reuse the longform processing pipeline.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.modules.audio.runtime.actor import capture_job_actor

from common_lib.modules.audio_processing.memory.feature_flags import (
    LONGFORM_ENABLED,
    is_enabled,
)
from common_lib.modules.audio_processing.services.podcast_service import PodcastSuite

import logging

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(capture_job_actor)])


class PodcastConfigRequest(BaseModel):
    target_lufs: float = Field(-16.0, ge=-70, le=0)
    true_peak_limit: float = Field(-1.0, ge=-6, le=0)
    sample_rate: int = Field(44100, gt=0)
    remove_silence: bool = True
    silence_threshold_db: float = Field(-45.0, ge=-80, le=0)
    silence_min_duration_ms: float = Field(500, ge=50)
    normalize: bool = True
    highpass_hz: float = Field(80.0, ge=20, le=200)
    denoise: bool = False


class ProcessEpisodeRequest(BaseModel):
    audio: str = Field(..., description="Path to input audio file")
    sample_rate: int = Field(44100, gt=0)
    config: Optional[PodcastConfigRequest] = None


class TrimSilenceRequest(BaseModel):
    audio: str = Field(..., description="Path to input audio file")
    sample_rate: int = Field(44100, gt=0)
    threshold_db: float = Field(-45.0, ge=-80, le=0)
    min_duration_ms: float = Field(500, ge=50)


class DetectChaptersRequest(BaseModel):
    audio: str = Field(..., description="Path to input audio file")
    sample_rate: int = Field(44100, gt=0)
    min_gap_seconds: float = Field(3.0, ge=0.5)
    energy_threshold_db: float = Field(-40.0, ge=-60, le=0)


class MultiGuestSplitRequest(BaseModel):
    audio: str = Field(..., description="Path to input audio file")
    sample_rate: int = Field(44100, gt=0)
    speaker_labels: List[str] = Field(..., min_items=1)
    timestamps: List[List[float]] = Field(..., min_items=1)


class GenerateShowNotesRequest(BaseModel):
    transcription_segments: List[Dict[str, Any]] = Field(default_factory=list)
    max_items: int = Field(10, ge=1, le=50)


class MultiGuestSplitResponse(BaseModel):
    tracks: Dict[str, str] = Field(default_factory=dict)


def _get_podcast_suite() -> PodcastSuite:
    """Get PodcastSuite instance (lazy singleton)."""
    if not hasattr(_get_podcast_suite, "_instance"):
        _get_podcast_suite._instance = PodcastSuite()
    return _get_podcast_suite._instance


@router.post(
    "/podcast/process",
    summary="Process podcast episode (cleanup, loudnorm, compressor, EQ, limiter)",
)
async def process_episode(req: ProcessEpisodeRequest) -> Dict[str, Any]:
    """Process a podcast episode through the full cleanup chain."""
    if not is_enabled(LONGFORM_ENABLED):
        raise HTTPException(
            status_code=404,
            detail="Podcast features disabled (LONGFORM_ENABLED flag is OFF)",
        )

    suite = _get_podcast_suite()
    config = req.config or PodcastConfigRequest()
    # For now return placeholder since actual audio loading not implemented in this endpoint
    return {
        "success": True,
        "message": "Podcast processing endpoint ready",
        "config": config.model_dump(),
    }


@router.post(
    "/podcast/trim-silence",
    summary="Trim silence from audio file",
)
async def trim_silence(req: TrimSilenceRequest) -> Dict[str, Any]:
    """Remove silence from audio file."""
    if not is_enabled(LONGFORM_ENABLED):
        raise HTTPException(status_code=404, detail="Podcast features disabled")

    # Would load audio from req.audio path
    return {"success": True, "message": "Silence trimming endpoint ready"}


@router.post(
    "/podcast/detect-chapters",
    summary="Detect chapter boundaries from silence gaps",
)
async def detect_chapters(req: DetectChaptersRequest) -> Dict[str, Any]:
    """Detect chapter boundaries from silence gaps in audio."""
    if not is_enabled(LONGFORM_ENABLED):
        raise HTTPException(status_code=404, detail="Podcast features disabled")

    # Would load audio from req.audio path
    return {
        "success": True,
        "message": "Chapter detection endpoint ready",
        "chapters": [],
    }


@router.post(
    "/podcast/multi-guest-split",
    summary="Split multi-guest recording into individual tracks",
)
async def multi_guest_split(req: MultiGuestSplitRequest) -> Dict[str, Any]:
    """Split multi-guest recording into individual tracks by speaker timestamps."""
    if not is_enabled(LONGFORM_ENABLED):
        raise HTTPException(status_code=404, detail="Podcast features disabled")

    # Would load audio from req.audio path
    return {
        "success": True,
        "message": "Multi-guest split endpoint ready",
        "tracks": {},
    }


@router.post(
    "/podcast/generate-show-notes",
    summary="Generate show notes from transcription segments",
)
async def generate_show_notes(req: GenerateShowNotesRequest) -> Dict[str, Any]:
    """Generate show notes (topics, timestamps, summary) from transcription."""
    if not is_enabled(LONGFORM_ENABLED):
        raise HTTPException(status_code=404, detail="Podcast features disabled")

    # Would process transcription segments
    return {
        "success": True,
        "message": "Show notes generation endpoint ready",
        "notes": {},
    }
