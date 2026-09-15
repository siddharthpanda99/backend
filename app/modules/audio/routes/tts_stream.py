"""Thin TTS chunked-stream + SSE events routers (C082 — W8-L06).

Provides:
- /stream/tts — Chunked audio streaming (async generator)
- /stream/events — Server-Sent Events for TTS progress

All routes delegate to common_lib services. No business logic here.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from common_lib.modules.audio_processing.memory.feature_flags import (
    TTS_STREAM_ENABLED,
    is_enabled,
)

router = APIRouter(prefix="/stream", tags=["Audio — Streaming"])


class TTSStreamRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize")
    voice_id: str = Field(default="default", description="Voice to use")
    model: str = Field(default="scenema", description="TTS model")
    chunk_size: int = Field(
        default=1024, ge=256, le=8192, description="Bytes per chunk"
    )
    sample_rate: int = Field(default=24000, description="Output sample rate")


async def _tts_chunk_generator(
    text: str,
    voice_id: str,
    model: str,
    chunk_size: int,
    sample_rate: int,
) -> AsyncGenerator[bytes, None]:
    """Generate TTS audio chunks by delegating to TTS service."""
    from common_lib.modules.audio_processing.services.tts_service import TTSService
    from common_lib.modules.audio_processing.generation.router import ModelRouter
    from common_lib.paths import GENERATED_CONTENT

    output_dir = GENERATED_CONTENT / "audio"
    tts = TTSService(str(output_dir), ModelRouter())

    from common_lib.modules.audio_processing.schemas import TTSRequest

    tts_req = TTSRequest(
        text=text,
        voice_id=voice_id,
        model=model,
        sample_rate=sample_rate,
    )

    # Use the streaming method if available
    try:
        async for chunk in tts.stream_tts(tts_req):
            if chunk:
                yield chunk
    except AttributeError:
        # Fallback: generate full audio and yield in chunks
        resp = await tts.generate_tts(tts_req)
        if resp.audio_bytes:
            data = resp.audio_bytes
            for i in range(0, len(data), chunk_size):
                yield data[i : i + chunk_size]
                await asyncio.sleep(0)  # Yield control


@router.post("/tts")
async def stream_tts(request: TTSStreamRequest, http_request: Request):
    """Chunked TTS audio streaming — POST /stream/tts

    Returns raw audio chunks as they are generated. Client should handle
    the streaming response and play/buffer chunks progressively.
    """
    if not is_enabled(TTS_STREAM_ENABLED):
        raise HTTPException(status_code=403, detail="TTS streaming disabled")

    async def generate():
        async for chunk in _tts_chunk_generator(
            request.text,
            request.voice_id,
            request.model,
            request.chunk_size,
            request.sample_rate,
        ):
            # Check for client disconnect
            if await http_request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="audio/wav",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# =============================================================================
# SSE Events
# =============================================================================


class SSEEvent(BaseModel):
    event: str
    data: str


async def _event_generator(request: Request, job_id: str) -> AsyncGenerator[str, None]:
    """Generate SSE events for a TTS job."""
    from common_lib.modules.audio_processing.library.batch_queue import get_batch_queue

    queue = get_batch_queue()

    # Send initial event
    yield f"event: started\ndata: {json.dumps({'job_id': job_id, 'status': 'started'})}\n\n"

    last_progress = -1.0
    while True:
        # Check for client disconnect
        if await request.is_disconnected():
            break

        job = await queue.get_job(job_id)
        if not job:
            yield f"event: error\ndata: {json.dumps({'job_id': job_id, 'error': 'Job not found'})}\n\n"
            break

        progress = job.get("progress", 0.0)
        status = job.get("status", "unknown")

        # Send progress updates
        if progress != last_progress:
            yield f"event: progress\ndata: {json.dumps({'job_id': job_id, 'progress': progress, 'status': status})}\n\n"
            last_progress = progress

        # Check for completion
        if status in ("completed", "failed", "cancelled"):
            event_data = {"job_id": job_id, "status": status}
            if status == "completed":
                event_data["result"] = job.get("result")
            elif status == "failed":
                event_data["error"] = job.get("error")
            yield f"event: {status}\ndata: {json.dumps(event_data)}\n\n"
            break

        await asyncio.sleep(0.5)  # Poll interval


@router.get("/events/{job_id}")
async def sse_events(request: Request, job_id: str):
    """Server-Sent Events for TTS job progress — GET /stream/events/{job_id}

    Returns a stream of SSE events: started, progress, completed/failed/cancelled.
    """
    if not is_enabled(TTS_STREAM_ENABLED):
        raise HTTPException(status_code=403, detail="TTS streaming disabled")

    from common_lib.modules.audio_processing.library.batch_queue import get_batch_queue

    queue = get_batch_queue()
    job = await queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return StreamingResponse(
        _event_generator(request, job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
