"""Audio Intelligence routes — thin transport layer.

Endpoints (prefix ``/intelligence``, mounted by the parent app under
``/api/v1/audio``):

- POST /intelligence/index                      — index a transcript into the RAG index
- POST /intelligence/search                      — semantic + keyword search
- POST /intelligence/rag/ask                     — retrieve answer context + citations (no LLM by default)
- GET  /intelligence/automation/jobs             — list registered automation jobs
- POST /intelligence/automation/jobs             — register a batch job
- POST /intelligence/automation/jobs/{job_id}/run — run a job now

All endpoints are gated behind the ``AUDIO_INTELLIGENCE_ENABLED`` environment
variable (default OFF): every endpoint returns 404 with a stable detail string
when the flag is not exactly ``true``. Handlers parse input, call one service
method, and shape output — business logic lives in common_lib.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.modules.audio.runtime.actor import capture_job_actor

from common_lib.modules.audio_processing.services.audio_automation_service import (
    AudioAutomationError,
    AudioAutomationService,
)
from common_lib.modules.audio_processing.services.audio_rag_service import (
    AudioRagError,
    AudioRagService,
)
from common_lib.modules.audio_processing.services.audio_search_service import (
    AudioSearchError,
    AudioSearchService,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    dependencies=[Depends(capture_job_actor)],
    prefix="/intelligence",
    tags=["Audio Intelligence"],
)

_FLAG_DETAIL = (
    "Audio intelligence features disabled (AUDIO_INTELLIGENCE_ENABLED flag is OFF)"
)


def _intelligence_enabled() -> bool:
    return os.getenv("AUDIO_INTELLIGENCE_ENABLED", "").strip().lower() == "true"


def _require_enabled() -> None:
    if not _intelligence_enabled():
        raise HTTPException(status_code=404, detail=_FLAG_DETAIL)


# ── shared service instances (lazy, one-time index load) ─────────────────────

_state: Dict[str, Any] = {}


def _rag() -> AudioRagService:
    if "rag" not in _state:
        service = AudioRagService()
        try:
            service.load_index()
        except Exception as exc:  # noqa: BLE001 - empty index is a valid state
            logger.debug("intelligence: no persisted rag index loaded (%s)", exc)
        _state["rag"] = service
    return _state["rag"]


def _search() -> AudioSearchService:
    if "search" not in _state:
        _state["search"] = AudioSearchService(rag_service=_rag())
    return _state["search"]


def _automation() -> AudioAutomationService:
    if "automation" not in _state:
        _state["automation"] = AudioAutomationService()
    return _state["automation"]


# ── Pydantic request models ───────────────────────────────────────────────────


class IndexTranscriptRequest(BaseModel):
    transcript_text: str = Field(
        ..., description="Full transcript text to chunk and index"
    )
    asset_id: str = Field(
        ..., description="Identifier of the source asset (path or caller token)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional metadata attached to every chunk (speaker, duration_s, project, ...)",
    )


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural-language query")
    top_k: int = Field(5, ge=1, le=50, description="Maximum hits to return")
    filters: Optional[Dict[str, Any]] = Field(
        None, description="Optional filters: {speaker, min_duration_s, redact}"
    )
    redact: bool = Field(
        False, description="Scrub PII (emails, phones, token URLs) from results"
    )


class RagAskRequest(BaseModel):
    query: str = Field(
        ..., min_length=1, description="Question to answer from indexed transcripts"
    )
    top_k: int = Field(5, ge=1, le=50, description="Chunks to retrieve")


class AutomationJobCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Human-readable job name")
    kind: str = Field(..., description="'transcribe_folder' or 'normalize_library'")
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Job parameters (folder, engine, dry_run, ...)",
    )
    schedule_cron: Optional[str] = Field(
        None, description="Recorded cron cadence (not executed by this module)"
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/index", summary="Index a transcript into the RAG index")
async def index_transcript(req: IndexTranscriptRequest) -> Dict[str, Any]:
    """Chunk + embed a transcript so it becomes searchable/askable."""
    _require_enabled()
    try:
        return _rag().index_transcript(
            transcript_text=req.transcript_text,
            asset_id=req.asset_id,
            metadata=req.metadata,
        )
    except AudioRagError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/search", summary="Semantic + keyword search over transcripts and assets")
async def search(req: SearchRequest) -> Dict[str, Any]:
    """Ranked hits across the RAG index and (if available) the asset library."""
    _require_enabled()
    try:
        return _search().search(
            query=req.query,
            top_k=req.top_k,
            filters=req.filters,
            redact=req.redact,
        )
    except AudioSearchError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post(
    "/rag/ask", summary="Retrieve answer context + citations (no LLM by default)"
)
async def rag_ask(req: RagAskRequest) -> Dict[str, Any]:
    """Build an answer context from the top-k chunks; never fabricates an answer."""
    _require_enabled()
    try:
        return _rag().ask(query=req.query, top_k=req.top_k)
    except AudioRagError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.get("/automation/jobs", summary="List registered automation jobs")
async def list_automation_jobs() -> Dict[str, Any]:
    """Return every registered batch job with its enabled state and last status."""
    _require_enabled()
    try:
        return _automation().list_jobs()
    except AudioAutomationError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc


@router.post("/automation/jobs", summary="Register an automation batch job")
async def create_automation_job(req: AutomationJobCreate) -> Dict[str, Any]:
    """Register a transcribe_folder or normalize_library batch job."""
    _require_enabled()
    try:
        return _automation().register_batch_job(
            {
                "name": req.name,
                "kind": req.kind,
                "params": req.params,
                "schedule_cron": req.schedule_cron,
            }
        )
    except AudioAutomationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/automation/jobs/{job_id}/run", summary="Run an automation job now")
async def run_automation_job(job_id: str) -> Dict[str, Any]:
    """Execute the job synchronously (dry-run semantics depend on the job params)."""
    _require_enabled()
    try:
        return _automation().run_now(job_id)
    except AudioAutomationError as exc:
        status = (
            404
            if exc.reason == "job_not_found"
            else 400
            if exc.reason in {"job_disabled", "bad_kind"}
            else 500
        )
        raise HTTPException(status_code=status, detail=exc.message) from exc
