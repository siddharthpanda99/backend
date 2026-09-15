"""Thin OpenAI-compat routes — /speech, /transcriptions, /voices (C081 — W8-L05).

All routes delegate to common_lib services. No business logic here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from common_lib.modules.audio_processing.memory.feature_flags import (
    OPENAI_COMPAT_ENABLED,
    is_enabled,
)

router = APIRouter(prefix="/openai", tags=["Audio — OpenAI Compat"])


class SpeechRequest(BaseModel):
    model: str = Field(default="tts-1", description="TTS model to use")
    input: str = Field(..., description="Text to synthesize")
    voice: str = Field(default="alloy", description="Voice to use")
    response_format: str = Field(
        default="mp3", description="Audio format: mp3, opus, aac, flac"
    )
    speed: float = Field(default=1.0, ge=0.25, le=4.0, description="Speech speed")


class TranscriptionRequest(BaseModel):
    model: str = Field(default="whisper-1", description="ASR model to use")
    language: str | None = Field(default=None, description="Input language (ISO-639-1)")
    prompt: str | None = Field(default=None, description="Optional context prompt")
    response_format: str = Field(
        default="json", description="Response format: json, text, srt, vtt"
    )
    temperature: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Sampling temperature"
    )


class VoiceInfo(BaseModel):
    id: str
    name: str
    category: str = "standard"


@router.post("/speech")
async def create_speech(request: SpeechRequest):
    """OpenAI-compatible TTS endpoint — POST /v1/audio/speech"""
    if not is_enabled(OPENAI_COMPAT_ENABLED):
        raise HTTPException(status_code=403, detail="OpenAI compat endpoints disabled")

    from common_lib.modules.audio_processing.services.tts_service import TTSService
    from common_lib.modules.audio_processing.generation.router import ModelRouter
    from common_lib.paths import GENERATED_CONTENT

    output_dir = GENERATED_CONTENT / "audio"
    router = ModelRouter()
    tts = TTSService(str(output_dir), router)

    from common_lib.modules.audio_processing.schemas import TTSRequest

    tts_req = TTSRequest(
        text=request.input,
        voice_id=request.voice,
        model=request.model,
        sample_rate=24000,
    )
    resp = await tts.generate_tts(tts_req, router)

    # Return audio bytes directly (OpenAI returns binary)
    from fastapi.responses import Response

    if resp.audio_bytes:
        return Response(
            content=resp.audio_bytes, media_type=f"audio/{request.response_format}"
        )
    raise HTTPException(status_code=500, detail="TTS generation failed")


@router.post("/transcriptions")
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form(default="whisper-1"),
    language: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    response_format: str = Form(default="json"),
    temperature: float = Form(default=0.0),
):
    """OpenAI-compatible transcription endpoint — POST /v1/audio/transcriptions"""
    if not is_enabled(OPENAI_COMPAT_ENABLED):
        raise HTTPException(status_code=403, detail="OpenAI compat endpoints disabled")

    from common_lib.modules.audio_processing.services.transcription_service import (
        TranscriptionService,
    )
    from common_lib.paths import GENERATED_CONTENT

    output_dir = GENERATED_CONTENT / "audio"
    transcription = TranscriptionService(str(output_dir))

    # Save uploaded file temporarily
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=f".{file.filename.split('.')[-1]}"
    ) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from common_lib.modules.audio_processing.schemas import TranscriptionRequest

        trans_req = TranscriptionRequest(
            audio_path=tmp_path,
            model=model,
            language=language or "auto",
        )
        resp = await transcription.transcribe(trans_req)

        if response_format == "json":
            return {"text": resp.text}
        elif response_format == "text":
            from fastapi.responses import PlainTextResponse

            return PlainTextResponse(resp.text)
        elif response_format in ("srt", "vtt"):
            # Return segments in SRT/VTT format
            from fastapi.responses import PlainTextResponse

            lines = []
            for i, seg in enumerate(resp.segments, 1):
                start = _format_timestamp(seg.start)
                end = _format_timestamp(seg.end)
                if response_format == "srt":
                    lines.append(f"{i}\n{start} --> {end}\n{seg.text}\n")
                else:
                    lines.append(f"{start} --> {end}\n{seg.text}\n")
            return PlainTextResponse("\n".join(lines))
        else:
            return {"text": resp.text}

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.get("/voices", response_model=list[VoiceInfo])
async def list_voices() -> list[VoiceInfo]:
    """OpenAI-compatible voices list — GET /v1/audio/voices"""
    if not is_enabled(OPENAI_COMPAT_ENABLED):
        raise HTTPException(status_code=403, detail="OpenAI compat endpoints disabled")

    from common_lib.modules.audio_processing.gallery.service import get_gallery_service

    gallery = get_gallery_service()
    if gallery is None:
        # Fallback to built-in voices
        return [
            VoiceInfo(id="alloy", name="Alloy"),
            VoiceInfo(id="echo", name="Echo"),
            VoiceInfo(id="fable", name="Fable"),
            VoiceInfo(id="onyx", name="Onyx"),
            VoiceInfo(id="nova", name="Nova"),
            VoiceInfo(id="shimmer", name="Shimmer"),
        ]

    # Try to get voices from gallery
    try:
        voices_data = await gallery.list_voices()
        return [
            VoiceInfo(
                id=v.get("voice_id", v.get("id", "")),
                name=v.get("name", ""),
                category=v.get("category", "custom"),
            )
            for v in voices_data
        ]
    except Exception:
        return [
            VoiceInfo(id="alloy", name="Alloy"),
            VoiceInfo(id="echo", name="Echo"),
            VoiceInfo(id="fable", name="Fable"),
            VoiceInfo(id="onyx", name="Onyx"),
            VoiceInfo(id="nova", name="Nova"),
            VoiceInfo(id="shimmer", name="Shimmer"),
        ]


def _format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS,mmm for SRT/VTT."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
