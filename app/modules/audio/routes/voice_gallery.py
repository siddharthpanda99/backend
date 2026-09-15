"""
Voice gallery + persona-bundle + describe + refinement parity routes (W4-L10).

Thin FastAPI routers — all logic delegated to common_lib services:
- ``gallery/service.py`` (archetype browse/search/download-plan)
- ``generation/voice_cloning/persona_bundle.py`` (.ovsvoice export/import)
- ``generation/voice_cloning/describe.py`` (LLM voice description)
- ``generation/refinement.py`` (post-generation refinement pass)

Flag gating is owned by the services themselves (VOICE_GALLERY_ENABLED,
OVSVOICE_ENABLED, VOICE_DESCRIBE_ENABLED, REFINEMENT_ENABLED — all default
OFF); each service returns a ``{"status": "disabled", ...}`` payload when its
flag is off, so these routes stay pure transport with zero flag logic.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from common_lib.modules.audio_processing.gallery.service import (
    get_archetype,
    list_archetypes,
    plan_download,
    search_gallery,
)
from common_lib.modules.audio_processing.generation.refinement import (
    refine_transcript,
)
from common_lib.modules.audio_processing.generation.voice_cloning.describe import (
    describe_voice_llm,
)
from common_lib.modules.audio_processing.generation.voice_cloning.persona_bundle import (
    export_bundle,
    import_bundle,
)

router = APIRouter()


# ── Request/Response Models ──────────────────────────────────────────────────


class BundleExportRequest(BaseModel):
    """.ovsvoice bundle export request."""

    profile: Dict[str, Any] = Field(..., description="Voice profile dict to bundle")
    ref_audio_b64: Optional[str] = Field(
        None, description="Base64 reference audio to embed (optional)"
    )
    license_spdx: Optional[str] = Field(None, description="SPDX license identifier")
    tags: Optional[List[str]] = Field(None, description="Discovery tags")


class BundleImportRequest(BaseModel):
    """.ovsvoice bundle import request."""

    bundle_b64: str = Field(..., description="Base64-encoded .ovsvoice bundle")


class VoiceDescribeRequest(BaseModel):
    """LLM voice-description request."""

    description: str = Field("", description="Free-text voice description to parse")
    attrs: Optional[Dict[str, str]] = Field(
        None, description="Explicit attribute overrides (gender/age/accent/...)"
    )


class RefinementRunRequest(BaseModel):
    """Refinement post-pass request."""

    text: str = Field(..., description="Transcript text to refine")
    use_llm: bool = Field(True, description="Allow the optional LLM polish pass")


# ── Persona bundles (.ovsvoice) ──────────────────────────────────────────────


@router.post("/voice/bundles/export")
async def export_voice_bundle(request: BundleExportRequest) -> Dict[str, Any]:
    """Export a voice profile as a .ovsvoice bundle (ZIP manifest+consent+SPDX)."""
    return export_bundle(
        profile=request.profile,
        ref_audio_b64=request.ref_audio_b64,
        license_spdx=request.license_spdx,
        tags=request.tags,
    )


@router.post("/voice/bundles/import")
async def import_voice_bundle(request: BundleImportRequest) -> Dict[str, Any]:
    """Import a .ovsvoice bundle (validates manifest/consent, returns profile)."""
    return import_bundle(request.bundle_b64)


# ── Voice gallery (archetype browse/search/download) ─────────────────────────


@router.get("/gallery/archetypes")
async def gallery_archetypes(
    use_case: Optional[str] = None, language: Optional[str] = None
) -> Dict[str, Any]:
    """List gallery archetype voice cards, optionally filtered."""
    return list_archetypes(use_case=use_case, language=language)


@router.get("/gallery/search")
async def gallery_search(query: str = "") -> Dict[str, Any]:
    """Search gallery archetypes by keyword."""
    return search_gallery(query=query)


@router.get("/gallery/archetypes/{archetype_id}")
async def gallery_archetype_detail(archetype_id: str) -> Dict[str, Any]:
    """Fetch one archetype card by ID."""
    return get_archetype(archetype_id)


@router.post("/gallery/download/plan")
async def gallery_download_plan(archetype_id: str) -> Dict[str, Any]:
    """Plan a gallery archetype download (returns download spec, no side effects)."""
    return plan_download(archetype_id)


# ── Voice describe + refinement ──────────────────────────────────────────────


@router.post("/voice/describe")
async def voice_describe(request: VoiceDescribeRequest) -> Dict[str, Any]:
    """LLM voice description → structured attributes (ai_gateway port, null-guarded)."""
    return describe_voice_llm(description=request.description, attrs=request.attrs)


@router.post("/refinement/run")
async def refinement_run(request: RefinementRunRequest) -> Dict[str, Any]:
    """Post-generation refinement pass (artifact collapse + optional LLM polish)."""
    return refine_transcript(text=request.text, use_llm=request.use_llm)
