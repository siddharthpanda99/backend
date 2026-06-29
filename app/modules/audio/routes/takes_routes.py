"""Generation Takes — API routes for versioned output tracking.

Provides:
- Unified ``POST /audio/generate`` — wraps any generation with take tracking
- ``GET /audio/takes/sessions`` — list active generation sessions
- ``GET /audio/takes/{session_id}`` — list takes for a session
- ``POST /audio/takes/{session_id}/promote/{take_number}`` — mark best take
- ``DELETE /audio/takes/{session_id}/take/{take_number}`` — delete a take
- ``POST /audio/takes/retry/{session_id}`` — retry the latest take
- ``POST /audio/takes/regenerate/{session_id}`` — regenerate (variation)

Mirrors Voicebox's elegant take-1/take-2/take-3 pattern for tracking
generation lineage while preserving all the existing generator endpoints.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.audio_processing.generation.takes_manager import (
    TakeRecord,
    SessionInfo,
    get_takes_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────


class UnifiedGenerateRequest(BaseModel):
    """Unified generation request with take tracking.

    Use this endpoint for ALL generation types to automatically get
    versioned takes (take-1, take-2, ...).
    """
    source: str = Field(
        ..., description="Generation type: tts | speak | music | sfx | voice_clone | singing | synth | edit"
    )
    mode: str = Field(
        default="generate",
        description="generate | retry | regenerate. "
                    "generate = fresh. retry = same params. regenerate = variation.",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters specific to the source type (e.g., text, voice, prompt, duration).",
    )
    intent_key: Optional[str] = Field(
        default=None,
        description="Logical grouping key. Auto-generated from params if omitted.",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed. None = random. Use same seed for reproducible output.",
    )


class SessionSummary(BaseModel):
    session_id: str
    source: str
    intent_key: str
    created_at: str
    take_count: int
    latest_take_number: Optional[int] = None
    promoted_take_number: Optional[int] = None


class TakeSummary(BaseModel):
    take_number: int
    mode: str
    output_url: str
    created_at: str
    promoted: bool
    seed: Optional[int] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    session_id: str
    take: TakeSummary
    output_url: str
    message: str = ""


class PromotionResponse(BaseModel):
    session_id: str
    take_number: int
    message: str


# ── Helper ───────────────────────────────────────────────────────────


def _compute_intent_key(source: str, params: Dict[str, Any]) -> str:
    """Generate a stable intent key from source and params.

    Uses a hash of normalized params so retry/regenerate of the same
    prompt lands in the same session.
    """
    # Build a stable string from the most relevant fields
    relevant = {
        k: params.get(k)
        for k in ("text", "prompt", "voice", "model_id", "description", "lyrics", "audio_path")
        if k in params
    }
    if not relevant:
        # Fall back to a hash of all params
        raw = json.dumps(params, sort_keys=True, default=str)
        relevant["_hash"] = str(hash(raw))

    normalized = json.dumps(relevant, sort_keys=True, default=str)
    short_hash = str(abs(hash(normalized)) % 10_000_000)
    return f"{source}_{short_hash}"


def _route_to_generator(source: str, params: Dict[str, Any]) -> Any:
    """Route a generation request to the appropriate backend service method.

    This keeps the unified endpoint decoupled from the service layer.
    Returns the response dict from the service call.
    """
    from common_lib.modules.audio_processing.service import audio_service
    from common_lib.modules.audio_processing.schemas import (
        TTSRequest,
        SpeakRequest,
        MusicGenRequest,
        SFXRequest,
        VoiceCloningRequest,
        SingingRequest,
    )

    source_map = {
        "tts": lambda: audio_service.generate_tts(
            TTSRequest(
                text=params.get("text", ""),
                description=params.get("description"),
                model_id=params.get("model_id"),
                voice=params.get("voice"),
                rate=params.get("rate", 1.0),
                pitch=params.get("pitch", 0.0),
                capability=params.get("capability", "realtime"),
                metadata=params.get("metadata"),
            )
        ),
        "speak": lambda: audio_service.generate_speak(
            SpeakRequest(
                xml_prompt=params.get("xml_prompt", ""),
                pace=params.get("pace", 1.0),
                seed=params.get("seed"),
                reference_audio=params.get("reference_audio"),
                background_sfx=params.get("background_sfx"),
                validate_speech=params.get("validate_speech", True),
                skip_vc=params.get("skip_vc", False),
                vc_diffusion_steps=params.get("vc_diffusion_steps", 20),
                vc_cfg_rate=params.get("vc_cfg_rate", 2.5),
            )
        ),
        "music": lambda: audio_service.generate_music(
            MusicGenRequest(
                prompt=params.get("prompt", ""),
                duration=params.get("duration", 8.0),
                key=params.get("key"),
                scale=params.get("scale"),
                bpm=params.get("bpm"),
                model=params.get("model"),
            )
        ),
        "sfx": lambda: audio_service.generate_sfx(
            SFXRequest(
                prompt=params.get("prompt", ""),
                duration=params.get("duration", 4.0),
                category=params.get("category", "ambient"),
                model=params.get("model"),
            )
        ),
        "voice_clone": lambda: audio_service.clone_voice(
            VoiceCloningRequest(
                text=params.get("text", ""),
                reference_audio_path=params.get("reference_audio_path", ""),
                model=params.get("model"),
                voice_profile_id=params.get("voice_profile_id"),
            )
        ),
        "singing": lambda: audio_service.synthesize_singing(
            SingingRequest(
                lyrics=params.get("lyrics", ""),
                notes=params.get("notes"),
                model=params.get("model"),
                vibrato_depth=params.get("vibrato_depth", 30),
                vibrato_rate=params.get("vibrato_rate", 5),
                breathiness=params.get("breathiness", 10),
                roughness=params.get("roughness", 0),
                pitch_correction=params.get("pitch_correction", 0),
            )
        ),
    }

    handler = source_map.get(source)
    if not handler:
        valid = ", ".join(sorted(source_map.keys()))
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source '{source}'. Valid sources: {valid}",
        )

    return handler()


# ── Endpoints ────────────────────────────────────────────────────────


@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Unified generation with take tracking",
    description="Generate audio (tts/speak/music/sfx/voice_clone/singing) with automatic take versioning. "
                "Use mode=generate for fresh, mode=retry to repeat, mode=regenerate for variation.",
)
async def unified_generate(req: UnifiedGenerateRequest) -> Dict[str, Any]:
    """Unified generation endpoint with automatic take tracking.

    All generation types flow through here and get versioned takes
    (take-1, take-2, ...). The ``mode`` field controls behavior:
      - ``generate``: Fresh generation with provided params.
      - ``retry``: Re-run with the same params and seed as the latest take.
      - ``regenerate``: Same params but seed=None for variation.
    """
    manager = get_takes_manager()
    intent_key = req.intent_key or _compute_intent_key(req.source, req.params)

    # Resolve params for retry/regenerate modes
    resolved_params = dict(req.params)
    resolved_seed = req.seed
    actual_mode = req.mode

    if req.mode == "retry":
        # Copy params from the latest take
        latest = manager.get_latest_take(req.source, intent_key)
        if latest:
            resolved_params = dict(latest.params)
            resolved_seed = latest.seed
        else:
            # No previous take — fall back to generate
            actual_mode = "generate"
            logger.info("No previous take for retry — falling back to generate")

    elif req.mode == "regenerate":
        # Copy params from latest take, but set seed=None for variation
        latest = manager.get_latest_take(req.source, intent_key)
        if latest:
            resolved_params = dict(latest.params)
            resolved_seed = None  # Variation
        else:
            actual_mode = "generate"
            logger.info("No previous take for regenerate — falling back to generate")

    try:
        # Route to the appropriate generator
        result = await _route_to_generator(req.source, resolved_params)

        # Extract output URL from result
        output_url = getattr(result, "audio_url", None) or getattr(result, "output_url", None) or ""
        output_path = getattr(result, "filename", None) or ""

        # Record the take (use actual_mode to reflect retry fallback to generate)
        take = manager.record_take(
            source=req.source,
            intent_key=intent_key,
            mode=actual_mode,
            output_path=output_path,
            output_url=output_url,
            params=resolved_params,
            seed=resolved_seed,
            metadata={
                "model": resolved_params.get("model") or resolved_params.get("model_id"),
                "duration": getattr(result, "duration_seconds", None),
                "audio_url": output_url,
            },
            session_metadata={
                "source": req.source,
                "intent_key": intent_key,
            },
        )

        return GenerateResponse(
            session_id=f"{req.source}/{intent_key}",
            take=TakeSummary(
                take_number=take.take_number,
                mode=take.mode,
                output_url=output_url,
                created_at=take.created_at,
                promoted=take.promoted,
                seed=take.seed,
                error=take.error,
                metadata=take.metadata,
            ),
            output_url=output_url,
            message=f"Take-{take.take_number} ({actual_mode}) generated successfully",
        ).model_dump()

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Generation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/takes/sessions",
    response_model=List[SessionSummary],
    summary="List generation sessions",
    description="Returns all active generation sessions with take counts.",
)
async def list_sessions(source: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """List all active generation sessions."""
    manager = get_takes_manager()
    sessions = manager.list_sessions(source=source, limit=limit)
    return [
        SessionSummary(
            session_id=s.session_id,
            source=s.source,
            intent_key=s.intent_key,
            created_at=s.created_at,
            take_count=s.take_count,
            latest_take_number=s.latest_take.take_number if s.latest_take else None,
            promoted_take_number=s.promoted_take.take_number if s.promoted_take else None,
        ).model_dump()
        for s in sessions
    ]


@router.get(
    "/takes/{session_id}",
    response_model=List[TakeSummary],
    summary="List takes for a session",
    description="Returns all takes for a given session, oldest first.",
)
async def list_takes(session_id: str) -> List[Dict[str, Any]]:
    """List all takes for a session."""
    manager = get_takes_manager()
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return [
        TakeSummary(
            take_number=t.take_number,
            mode=t.mode,
            output_url=t.output_url,
            created_at=t.created_at,
            promoted=t.promoted,
            seed=t.seed,
            error=t.error,
            metadata=t.metadata,
        ).model_dump()
        for t in session.takes
    ]


@router.post(
    "/takes/{session_id}/promote/{take_number}",
    response_model=PromotionResponse,
    summary="Promote a take to best",
    description="Mark a specific take as the preferred version for its session.",
)
async def promote_take(session_id: str, take_number: int) -> Dict[str, Any]:
    """Mark a take as the preferred/best version."""
    manager = get_takes_manager()
    parts = session_id.split("/", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail=f"Invalid session_id format: {session_id}")

    source, intent_key = parts
    take = manager.promote_take(source, intent_key, take_number)
    if not take:
        raise HTTPException(
            status_code=404,
            detail=f"Take-{take_number} not found in session '{session_id}'",
        )

    return PromotionResponse(
        session_id=session_id,
        take_number=take_number,
        message=f"Take-{take_number} promoted to best in session '{session_id}'",
    ).model_dump()


@router.delete(
    "/takes/{session_id}/take/{take_number}",
    summary="Delete a take",
    description="Remove a specific take from its session.",
)
async def delete_take(session_id: str, take_number: int) -> Dict[str, Any]:
    """Delete a specific take."""
    manager = get_takes_manager()
    parts = session_id.split("/", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail=f"Invalid session_id format: {session_id}")

    source, intent_key = parts
    deleted = manager.delete_take(source, intent_key, take_number)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Take-{take_number} not found in session '{session_id}'",
        )

    return {"status": "ok", "message": f"Take-{take_number} deleted from '{session_id}'"}


@router.post(
    "/takes/retry/{session_id}",
    response_model=GenerateResponse,
    summary="Retry the latest take",
    description="Re-runs generation with the same params and seed as the latest take in the session.",
)
async def retry_latest(session_id: str) -> Dict[str, Any]:
    """Retry the latest take in a session (same params, same seed)."""
    manager = get_takes_manager()
    parts = session_id.split("/", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail=f"Invalid session_id: {session_id}")

    source, intent_key = parts
    latest = manager.get_latest_take(source, intent_key)
    if not latest:
        raise HTTPException(status_code=404, detail=f"No takes found for session '{session_id}'")

    return await unified_generate(UnifiedGenerateRequest(
        source=source,
        mode="retry",
        params=latest.params,
        intent_key=intent_key,
        seed=latest.seed,
    ))


@router.post(
    "/takes/regenerate/{session_id}",
    response_model=GenerateResponse,
    summary="Regenerate the latest take (variation)",
    description="Re-runs generation with the same params but seed=None to produce a variation.",
)
async def regenerate_latest(session_id: str) -> Dict[str, Any]:
    """Regenerate the latest take (same params, seed=None for variation)."""
    manager = get_takes_manager()
    parts = session_id.split("/", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail=f"Invalid session_id: {session_id}")

    source, intent_key = parts
    latest = manager.get_latest_take(source, intent_key)
    if not latest:
        raise HTTPException(status_code=404, detail=f"No takes found for session '{session_id}'")

    return await unified_generate(UnifiedGenerateRequest(
        source=source,
        mode="regenerate",
        params=latest.params,
        intent_key=intent_key,
    ))


@router.get(
    "/takes/stats",
    summary="Take system statistics",
    description="Returns aggregate statistics about all sessions and takes.",
)
async def takes_stats() -> Dict[str, Any]:
    """Get aggregate statistics about the takes system."""
    return get_takes_manager().get_stats()


__all__ = ["router"]
