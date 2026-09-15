"""NLP text preprocessing thin routes (C013 — W1-L05, gap N6).

Transport ONLY: delegates every operation to the common_lib TTS text-side
modules (`normalize_for_tts`, `parse_ssml_lite` + `spell_out`, `polish_text` /
`polish_text_llm`). No business logic here — the platform boundary rule keeps
all logic in common_lib.

Gating mirrors the service layer: `normalize` and `polish(llm=...)` honor
`AUDIO_TTS_TEXT_NORMALIZATION` / the `NLP_PREPROCESS_ENABLED` feature flag
(default OFF) inside common_lib, so these routes are inert until the flag is
enabled — the response simply echoes the input text back unchanged.
`ssml/apply` and `polish` (deterministic) are pure and ungated.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request / response schemas (transport-local, additive) ────────────────────


class NlpNormalizeRequest(BaseModel):
    text: str = Field(..., description="Raw text to normalize")
    language: Optional[str] = Field(
        None, description="Display name or ISO code, e.g. 'English' or 'en'"
    )
    force: bool = Field(
        False,
        description="Run the pure normalization pass even when the flag is off",
    )


class NlpNormalizeResponse(BaseModel):
    text: str
    language: Optional[str] = None
    applied: bool = Field(..., description="Whether normalization actually ran")


class NlpSsmlApplyRequest(BaseModel):
    text: str = Field(..., description="One line possibly containing [slow]/[fast]/[emphasis]/[spell] tags")


class NlpSsmlSegment(BaseModel):
    text: str
    speed: Optional[float] = None
    spell: bool = False
    emphasis: bool = False


class NlpSsmlApplyResponse(BaseModel):
    segments: list[NlpSsmlSegment]
    plain_text: str = Field(
        "", description="Tag markers stripped, [spell] expanded when requested"
    )


class NlpPolishRequest(BaseModel):
    text: str = Field(..., description="Text to polish")
    llm: bool = Field(
        False,
        description="Additionally run the optional LLM pass (ai_gateway port; passthrough when unavailable)",
    )
    language: Optional[str] = Field(
        None, description="Language hint for the LLM pass"
    )


class NlpPolishResponse(BaseModel):
    text: str
    deterministic: str = Field(
        ..., description="Result of the deterministic polish pass"
    )
    llm_applied: bool = Field(
        ..., description="Whether the LLM pass changed the text"
    )


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("/nlp/normalize", response_model=NlpNormalizeResponse)
async def normalize_text(data: NlpNormalizeRequest):
    """Normalize text for TTS (gated; `force` bypasses the gate for the pure pass)."""
    from common_lib.modules.audio_processing.generation.tts.text_normalization import (
        normalize_for_tts,
        normalize_text,
    )

    try:
        if data.force:
            out = normalize_text(data.text, data.language)
            applied = out != data.text
        else:
            out = normalize_for_tts(data.text, data.language)
            applied = out != data.text
        return NlpNormalizeResponse(text=out, language=data.language, applied=applied)
    except Exception as exc:  # noqa: BLE001 — never leak internals
        logger.warning("nlp/normalize failed: %s", exc)
        return NlpNormalizeResponse(text=data.text, language=data.language, applied=False)


@router.post("/nlp/ssml/apply", response_model=NlpSsmlApplyResponse)
async def apply_ssml_lite(data: NlpSsmlApplyRequest):
    """Parse SSML-lite inline markup into prosody segments."""
    from common_lib.modules.audio_processing.generation.tts.ssml_lite import (
        parse_ssml_lite,
        spell_out,
    )

    # Source semantics (VoiceStudio longform_parser): [spell] runs are
    # expanded per-segment via the markup flag — never forced globally,
    # which would mangle unmarked segments.
    segments = parse_ssml_lite(data.text)
    plain = ""
    for seg in segments:
        piece = spell_out(seg["text"]) if seg["spell"] else seg["text"]
        plain += piece
    return NlpSsmlApplyResponse(
        segments=[NlpSsmlSegment(**seg) for seg in segments],
        plain_text=plain,
    )


@router.post("/nlp/polish", response_model=NlpPolishResponse)
async def polish_text(data: NlpPolishRequest):
    """Polish text deterministically, optionally followed by the LLM pass."""
    from common_lib.modules.audio_processing.generation.tts.polish import (
        polish_text_llm,
        polish_text,
    )

    try:
        det = polish_text(data.text)
    except Exception as exc:  # noqa: BLE001 — polish never breaks the request
        logger.warning("nlp/polish deterministic failed: %s", exc)
        det = data.text

    llm_applied = False
    out = det
    if data.llm and det.strip():
        try:
            llm_out = polish_text_llm(det, data.language)
            llm_applied = llm_out != det
            out = llm_out
        except Exception as exc:  # noqa: BLE001 — LLM pass is optional
            logger.warning("nlp/polish llm pass failed: %s", exc)

    return NlpPolishResponse(text=out, deterministic=det, llm_applied=llm_applied)
