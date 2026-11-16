"""Voice consent + watermark routes — thin transport layer.

Endpoints
---------
Consent ledger (ALWAYS available — safety/compliance feature, not flag-gated):
  POST   /consent                       — record a voice consent
  GET    /consent?voice_profile_id=&include_revoked=  — list consents (newest first)
  POST   /consent/{consent_id}/revoke   — revoke one consent row
  GET    /consent/{consent_id}/status   — fetch one consent row + derived status
  POST   /consent/assert                — {allowed, reason} decision for a requested use

Watermark (ALWAYS available — provenance feature, not flag-gated):
  POST   /watermark/embed               — embed spread-spectrum watermark into a file
  POST   /watermark/extract             — check whether a watermark survives

Both routers carry ``Depends(capture_job_actor)``. Business logic is delegated
to the common_lib services; this file only parses input and shapes errors.

Error mapping:
  ConsentError / VoiceConsentError  → 400 (bad request) / 404 (not found) / 500
  WatermarkError is reported inside the service dict (ok=false) → 200 with
  ``{"ok": false, "error": ...}`` so pipelines can branch on the flag.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.modules.audio.runtime.actor import capture_job_actor

from common_lib.modules.audio_processing.services import watermarking
from common_lib.modules.audio_processing.services.consent_service import (
    ConsentService,
    VoiceConsentError,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    dependencies=[Depends(capture_job_actor)],
    prefix="/consent",
    tags=["Voice Consent"],
)

watermark_router = APIRouter(
    dependencies=[Depends(capture_job_actor)],
    prefix="/watermark",
    tags=["Audio Watermark"],
)

_consent_service: Optional[ConsentService] = None


def _get_consent_service() -> ConsentService:
    """Lazy singleton — avoids creating the sqlite ledger at import/collection time."""
    global _consent_service
    if _consent_service is None:
        _consent_service = ConsentService()
    return _consent_service


# ── Pydantic models ───────────────────────────────────────────────────────────


class ConsentCreate(BaseModel):
    voice_profile_id: str = Field(
        ..., min_length=1, description="Voice profile the consent applies to"
    )
    subject_name: str = Field(
        ..., min_length=1, description="Name of the consenting subject"
    )
    scope: list[str] = Field(
        ...,
        min_length=1,
        description="Allowed uses, e.g. ['tts', 'conversion', 'songs']",
    )
    subject_role: str = Field(
        "self",
        description="'self' when the subject is the requester, else e.g. 'non-self'",
    )
    expires_at: Optional[datetime] = Field(
        None, description="ISO-8601 expiry timestamp (optional)"
    )
    evidence_ref: Optional[str] = Field(
        None,
        description="Reference to supporting evidence (signed release, email, ...)",
    )
    restrictions: Optional[dict] = Field(
        None,
        description="Free-form restrictions (territory, term, purpose limits, ...)",
    )


class ConsentAssert(BaseModel):
    voice_profile_id: str = Field(..., min_length=1)
    requested_use: str = Field(
        ...,
        min_length=1,
        description="Requested use, e.g. 'tts', 'conversion', 'singing', 'songs'",
    )


class WatermarkEmbedRequest(BaseModel):
    in_path: str = Field(
        ..., min_length=1, description="Input audio file (any format ffmpeg reads)"
    )
    out_path: str = Field(..., min_length=1, description="Output WAV path")
    asset_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)


class WatermarkExtractRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Audio file to inspect")
    asset_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _map_consent_error(exc: VoiceConsentError) -> HTTPException:
    message = exc.message
    if "not found" in message:
        return HTTPException(status_code=404, detail=message)
    if "required" in message or "must" in message:
        return HTTPException(status_code=400, detail=message)
    return HTTPException(status_code=500, detail=message)


# ── Consent endpoints ─────────────────────────────────────────────────────────


@router.post("")
async def create_consent(body: ConsentCreate) -> dict[str, Any]:
    """Record a revocable voice consent. Always available (safety feature)."""
    try:
        return _get_consent_service().create_consent(
            body.voice_profile_id,
            body.subject_name,
            body.scope,
            expires_at=body.expires_at,
            evidence_ref=body.evidence_ref,
            restrictions=body.restrictions,
            subject_role=body.subject_role,
        )
    except VoiceConsentError as exc:
        raise _map_consent_error(exc) from exc


@router.get("")
async def list_consents(
    voice_profile_id: Optional[str] = Query(None),
    include_revoked: bool = Query(False),
) -> dict[str, Any]:
    """List consent rows (newest first), optionally filtered by profile."""
    try:
        consents = _get_consent_service().list_consents(
            profile_id=voice_profile_id,
            include_revoked=include_revoked,
        )
    except VoiceConsentError as exc:
        raise _map_consent_error(exc) from exc
    return {"consents": consents, "count": len(consents)}


@router.post("/{consent_id}/revoke")
async def revoke_consent(consent_id: int) -> dict[str, Any]:
    """Revoke one consent row by id."""
    try:
        return _get_consent_service().revoke_consent(consent_id=consent_id)
    except VoiceConsentError as exc:
        raise _map_consent_error(exc) from exc


@router.get("/{consent_id}/status")
async def consent_status(consent_id: int) -> dict[str, Any]:
    """Fetch one consent row plus a derived status string."""
    try:
        row = _get_consent_service().get_consent(consent_id)
    except VoiceConsentError as exc:
        raise _map_consent_error(exc) from exc

    now = datetime.now(timezone.utc)
    expires = row.get("expires_at")
    status = "active"
    if row.get("revoked_at"):
        status = "revoked"
    elif expires:
        try:
            exp_dt = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=now.tzinfo)
            if exp_dt <= now:
                status = "expired"
        except ValueError:
            status = "unknown"
    return {**row, "status": status}


@router.post("/assert")
async def assert_consent(body: ConsentAssert) -> dict[str, Any]:
    """Decision endpoint: may this profile be used for ``requested_use``?"""
    try:
        return _get_consent_service().assert_active(body.voice_profile_id, body.requested_use)
    except VoiceConsentError as exc:
        raise _map_consent_error(exc) from exc


# ── Watermark endpoints ───────────────────────────────────────────────────────


@watermark_router.post("/embed")
async def watermark_embed(body: WatermarkEmbedRequest) -> dict[str, Any]:
    """Embed the spread-spectrum watermark; returns stats in the payload."""
    return watermarking.embed_file(
        body.in_path, body.out_path, body.asset_id, body.trace_id
    )


@watermark_router.post("/extract")
async def watermark_extract(body: WatermarkExtractRequest) -> dict[str, Any]:
    """Check whether the watermark for the payload survives in the file."""
    return watermarking.extract_file(body.path, body.asset_id, body.trace_id)
