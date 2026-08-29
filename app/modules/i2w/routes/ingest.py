"""``app.modules.i2w.routes.ingest`` — Stage 1 ingest endpoints.

Mounts (per docs/08_api_contract.md §1.2):

* ``POST /api/v1/i2w/ingest/audio``
* ``POST /api/v1/i2w/ingest/text``
* ``POST /api/v1/i2w/ingest/screenshot``
* ``POST /api/v1/i2w/ingest/screen-recording``
* ``POST /api/v1/i2w/ingest/file``
* ``POST /api/v1/i2w/ingest/multi``
* ``GET  /api/v1/i2w/health/ingest``   (defined in routes/health.py)

Plus the Stage 1 health probe, all wired to the corresponding
``i2w_ingest_*`` @node wrapper.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status

from app.modules.i2w.routes._helpers import invoke_i2w
from app.modules.i2w.routes.dependencies import (
    I2W_SCOPE_WRITE,
    _audit_request,
    i2w_deps,
    i2w_identity,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _body_to_kwargs(body: Dict[str, Any]) -> Dict[str, Any]:
    """Pass-through — the wrapper owns the contract."""
    return dict(body)


async def _invoke_ingest(
    request: Request,
    body: Dict[str, Any],
    *,
    wrapper: str,
    action: str,
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    trace_id = request.headers.get("X-Trace-ID", "")
    defaults: Dict[str, Any] = {
        "user_id_hash": str(getattr(identity, "subject_id", "anon")),
        "tenant_id": str(getattr(identity, "tenant_id", "default")),
    }
    if trace_id:
        defaults["trace_id"] = trace_id
    try:
        result = invoke_i2w(wrapper, defaults=defaults, **_body_to_kwargs(body))
    except RuntimeError as exc:
        _audit_request(request, identity, action=action, status_code=400)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    _audit_request(request, identity, action=action)
    return result


# ---------------------------------------------------------------------------
# POST /ingest/audio
# ---------------------------------------------------------------------------


@router.post(
    "/ingest/audio",
    summary="Ingest a voice instruction (audio ref + metadata).",
    description=(
        "Body: { audio_ref, user_id_hash, tenant_id, locale? }. The "
        "wrapper downloads the audio, transcribes, redacts PII, and "
        "returns a ``RawInstruction``."
    ),
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="ingest"),
    response_model=None,
)
async def ingest_audio(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _invoke_ingest(
        request, body, wrapper="i2w_ingest_audio", action="i2w.ingest.audio"
    )


# ---------------------------------------------------------------------------
# POST /ingest/text
# ---------------------------------------------------------------------------


@router.post(
    "/ingest/text",
    summary="Ingest a typed text instruction.",
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="ingest"),
    response_model=None,
)
async def ingest_text(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _invoke_ingest(
        request, body, wrapper="i2w_ingest_text", action="i2w.ingest.text"
    )


# ---------------------------------------------------------------------------
# POST /ingest/screenshot
# ---------------------------------------------------------------------------


@router.post(
    "/ingest/screenshot",
    summary="Ingest a screenshot (image ref).",
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="ingest"),
    response_model=None,
)
async def ingest_screenshot(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _invoke_ingest(
        request,
        body,
        wrapper="i2w_ingest_screenshot",
        action="i2w.ingest.screenshot",
    )


# ---------------------------------------------------------------------------
# POST /ingest/screen-recording
# ---------------------------------------------------------------------------


@router.post(
    "/ingest/screen-recording",
    summary="Ingest a screen recording (video ref).",
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="ingest"),
    response_model=None,
)
async def ingest_screen_recording(
    request: Request, body: Dict[str, Any]
) -> Dict[str, Any]:
    return await _invoke_ingest(
        request,
        body,
        wrapper="i2w_ingest_screen_recording",
        action="i2w.ingest.screen_recording",
    )


# ---------------------------------------------------------------------------
# POST /ingest/file
# ---------------------------------------------------------------------------


@router.post(
    "/ingest/file",
    summary="Ingest a file attachment (PDF, doc, image, etc.).",
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="ingest"),
    response_model=None,
)
async def ingest_file(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _invoke_ingest(
        request, body, wrapper="i2w_ingest_file", action="i2w.ingest.file"
    )


# ---------------------------------------------------------------------------
# POST /ingest/multi
# ---------------------------------------------------------------------------


@router.post(
    "/ingest/multi",
    summary="Ingest a multi-modal instruction (text + audio + image).",
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="ingest"),
    response_model=None,
)
async def ingest_multi(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _invoke_ingest(
        request, body, wrapper="i2w_ingest_multi", action="i2w.ingest.multi"
    )


__all__ = ["router"]
