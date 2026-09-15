"""Dubbing thin routes (W6-L07, C067+C068, gap N1). ALL logic delegates to
``common_lib.modules.audio_processing.dubbing`` via lazy imports — no
business logic here (thin-router rule). Endpoints:

- ``POST   /dub/jobs``                    — create a dub job
- ``GET    /dub/jobs``                    — list jobs
- ``GET    /dub/jobs/{job_id}``           — job status (full dict)
- ``DELETE /dub/jobs/{job_id}``           — delete a job
- ``POST   /dub/jobs/{job_id}/state``     — validated state transition
- ``POST   /dub/generate``                — plan a generate scope (+ preview params)
- ``POST   /dub/regen``                   — partial-regen scope decision
- ``POST   /dub/preview``                 — fast-preview TTS params
- ``POST   /dub/timing``                  — timing plan for a track
- ``POST   /dub/clone``                   — per-speaker clone extraction
- ``POST   /dub/ingest-url``              — SSRF-guarded URL ingest
- ``POST   /dub/qc``                      — second-pass QC scoring
- ``POST   /dub/export``                  — retime decision for export muxing
- ``POST   /dub/abort/{job_id}``          — abort + kill in-flight work
- ``GET    /dub/status/{job_id}``         — SSE progress stream (heartbeat)

Endpoints return 503 with ``{"detail": {"status": "disabled", ...}}`` when
``DUBBING_ENABLED`` is OFF (route surface stays mounted for discoverability).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

_FLAG = "DUBBING_ENABLED"


def _flag_on() -> bool:
    from common_lib.modules.audio_processing.memory import feature_flags as ff

    return bool(ff.is_enabled(_FLAG))


def _require_flag() -> None:
    if not _flag_on():
        raise HTTPException(
            status_code=503,
            detail={"status": "disabled", "flag": _FLAG,
                    "reason": "Dubbing flag is OFF"},
        )


# ── Request models ──────────────────────────────────────────────────────────


class DubJobCreate(BaseModel):
    job_id: str | None = None
    input_kind: str = "file"
    source_path: str = ""
    source_lang: str = ""
    target_lang: str = ""
    options: dict[str, Any] = Field(default_factory=dict)


class DubStateRequest(BaseModel):
    to_state: str
    error: str = ""


class DubGenerateRequest(BaseModel):
    job_id: str
    content_hash: str = ""
    segments: list[dict[str, Any]] = Field(default_factory=list)
    natural_durs_s: list[float] = Field(default_factory=list)
    total_dur_s: float = 0.0
    timing_strategy: str = "smart_fit"
    preview: bool = False
    options: dict[str, Any] = Field(default_factory=dict)


class DubRegenRequest(BaseModel):
    job_id: str
    regen_only: list[str] | None = None
    timing_strategy: str = "concise"
    lang_code: str = ""


class DubTimingRequest(BaseModel):
    segments: list[dict[str, Any]]
    natural_durs_s: list[float]
    total_dur_s: float = 0.0
    strategy: str = "smart_fit"


class DubCloneRequest(BaseModel):
    audio_path: str = ""
    out_dir: str = ""
    vocals_path: str = ""
    segments: list[dict[str, Any]] = Field(default_factory=list)
    labels_source: str | None = None


class DubIngestUrlRequest(BaseModel):
    url: str
    out_dir: str = ""
    fetch_subs: bool = True
    sub_langs: list[str] | None = None


class DubQCRequest(BaseModel):
    dub_segments: list[dict[str, Any]]
    recognized: list[dict[str, Any]] = Field(default_factory=list)
    drift_threshold: float = 0.5


class DubExportRequest(BaseModel):
    job_id: str
    plan: list[dict[str, Any]] = Field(default_factory=list)
    orig_dur: float = 0.0
    track_dur: float = 0.0


# ── Jobs CRUD (C067) ────────────────────────────────────────────────────────


@router.post("/dub/jobs", status_code=201)
async def create_dub_job(req: DubJobCreate):
    """Create a dub job (queued state). Generates an 8-char id when omitted."""
    _require_flag()
    import uuid

    from common_lib.modules.audio_processing.dubbing import pipeline as dp

    job_id = req.job_id or str(uuid.uuid4())[:8]
    out = dp.node_create_job(
        job_id,
        input_kind=req.input_kind,
        source_path=req.source_path,
        source_lang=req.source_lang,
        target_lang=req.target_lang,
        options=req.options,
    )
    if out.get("status") == "disabled":
        raise HTTPException(status_code=503, detail=out)
    if out.get("status") != "ok":
        raise HTTPException(status_code=400, detail=out.get("reason", "invalid job"))
    return out["job"]


@router.get("/dub/jobs")
async def list_dub_jobs():
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import pipeline as dp

    return {"jobs": dp.list_jobs()}


@router.get("/dub/jobs/{job_id}")
async def get_dub_job(job_id: str):
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import pipeline as dp

    job = dp.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"dub job {job_id} not found")
    return job


@router.delete("/dub/jobs/{job_id}")
async def delete_dub_job(job_id: str):
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import pipeline as dp

    if not dp.delete_job(job_id):
        raise HTTPException(status_code=404, detail=f"dub job {job_id} not found")
    return {"deleted": job_id}


@router.post("/dub/jobs/{job_id}/state")
async def set_dub_job_state(job_id: str, req: DubStateRequest):
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import pipeline as dp

    out = dp.node_update_state(job_id, req.to_state, error=req.error)
    if out.get("status") == "disabled":
        raise HTTPException(status_code=503, detail=out)
    if out.get("status") != "ok":
        reason = str(out.get("reason", ""))
        if "not found" in reason:
            raise HTTPException(status_code=404, detail=reason)
        raise HTTPException(status_code=409, detail=reason)
    return out["job"]


# ── Generate / regen / preview (C067 + C068) ────────────────────────────────


@router.post("/dub/generate")
async def dub_generate(req: DubGenerateRequest):
    """Plan a generate run: hash-cache lookup, timing plan, regen scope, and
    (for preview) the fast-preview TTS params. Heavy engine execution stays
    behind the worker bridge — this is the thin planning surface."""
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import pipeline as dp
    from common_lib.modules.audio_processing.dubbing import timing as dub_timing

    # Resolve the job (404 when unknown).
    job = dp.get_job(req.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"dub job {req.job_id} not found")

    content_hash = req.content_hash or (job.get("content_hash") or "")
    cache_hit = None
    if content_hash:
        hit = dp.find_cached_job(content_hash, exclude_job_id=req.job_id)
        cache_hit = hit

    plan_out = dub_timing.node_plan_timing(
        req.segments, req.natural_durs_s, req.total_dur_s,
        strategy=req.timing_strategy,
    )
    if plan_out.get("status") == "disabled":
        raise HTTPException(status_code=503, detail=plan_out)
    if plan_out.get("status") != "ok":
        raise HTTPException(status_code=400, detail=plan_out.get("reason"))

    regen = dp.plan_regen(
        job, None, timing_strategy=req.timing_strategy,
    )
    options = dp.preview_params(req.options, preview=req.preview)

    return {
        "job_id": req.job_id,
        "content_hash": content_hash,
        "cache_hit": cache_hit,
        "timing": plan_out,
        "regen_scope": regen,
        "options": options,
    }


@router.post("/dub/regen")
async def dub_regen(req: DubRegenRequest):
    """Partial-regen scope decision for a job (reuse on-disk segment WAVs)."""
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import pipeline as dp

    job = dp.get_job(req.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"dub job {req.job_id} not found")
    out = dp.node_plan_regen(
        job, req.regen_only,
        timing_strategy=req.timing_strategy,
        lang_code=req.lang_code,
    )
    if out.get("status") == "disabled":
        raise HTTPException(status_code=503, detail=out)
    return out


@router.post("/dub/preview")
async def dub_preview(req: DubGenerateRequest):
    """Fast-preview TTS params for interactive edits (halved diffusion steps)."""
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import pipeline as dp

    if dp.get_job(req.job_id) is None:
        raise HTTPException(status_code=404, detail=f"dub job {req.job_id} not found")
    return {"job_id": req.job_id, "options": dp.preview_params(req.options, preview=True)}


# ── Timing / clone / ingest / QC / export (C068) ────────────────────────────


@router.post("/dub/timing")
async def dub_timing_route(req: DubTimingRequest):
    """Timing plan (per-segment rates / video ratios / placement)."""
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import timing as dub_timing

    out = dub_timing.node_plan_timing(
        req.segments, req.natural_durs_s, req.total_dur_s,
        strategy=req.strategy,
    )
    if out.get("status") == "disabled":
        raise HTTPException(status_code=503, detail=out)
    if out.get("status") != "ok":
        raise HTTPException(status_code=400, detail=out.get("reason"))
    return out


@router.post("/dub/clone")
async def dub_clone(req: DubCloneRequest):
    """Extract per-speaker clone references (via the stem-separator port)."""
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import speaker_clone as sc

    vocals = sc.ensure_vocals_track(
        req.audio_path, req.out_dir, vocals_path=req.vocals_path or None,
    )
    if req.vocals_path and not vocals:
        vocals = req.vocals_path
    if not vocals:
        return {"status": "ok", "found": False, "clones": {}, "refs": {}}
    clones = sc.extract_speaker_clones(
        vocals, req.segments, req.out_dir, labels_source=req.labels_source,
    )
    refs = sc.extract_segment_refs(vocals, req.segments, req.out_dir)
    return {"status": "ok", "found": True, "vocals_path": vocals,
            "clones": clones, "refs": refs}


@router.post("/dub/ingest-url")
async def dub_ingest_url(req: DubIngestUrlRequest):
    """SSRF-guarded URL ingest (yt-dlp media + subtitles)."""
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import ingest as dub_ingest

    out_dir = req.out_dir
    if not out_dir:
        digest = hashlib.sha256(req.url.encode()).hexdigest()[:12]
        out_dir = os.path.join(tempfile.gettempdir(), f"dub_ingest_{digest}")
        os.makedirs(out_dir, exist_ok=True)
    out = dub_ingest.ingest_url(
        req.url, out_dir, fetch_subs=req.fetch_subs, sub_langs=req.sub_langs,
    )
    if out.get("status") == "error":
        raise HTTPException(status_code=400, detail=out.get("reason", "ingest failed"))
    return out


@router.post("/dub/qc")
async def dub_qc_route(req: DubQCRequest):
    """Second-pass QC scoring against pre-recognized segments."""
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import qc as dub_qc

    out = dub_qc.node_score_qc(
        req.dub_segments, req.recognized, drift_threshold=req.drift_threshold,
    )
    if out.get("status") == "disabled":
        raise HTTPException(status_code=503, detail=out)
    return out


@router.post("/dub/export")
async def dub_export(req: DubExportRequest):
    """Retime decision for the export mux (filter graph or retimed file)."""
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import video_retime as vr

    out = vr.node_build_retime_graph(req.plan, req.orig_dur, track_dur=req.track_dur)
    if out.get("status") == "disabled":
        raise HTTPException(status_code=503, detail=out)
    if out.get("status") != "ok":
        raise HTTPException(status_code=400, detail=out.get("reason"))
    return out


# ── Abort + SSE (C068) ──────────────────────────────────────────────────────


@router.post("/dub/abort/{job_id}")
async def dub_abort(job_id: str):
    """Abort an in-flight job: cooperative flag + subprocess kill + transition."""
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import pipeline as dp

    out = dp.abort_job(job_id)
    if out.get("state") == "missing":
        raise HTTPException(status_code=404, detail=f"dub job {job_id} not found")
    return out


@router.get("/dub/status/{job_id}")
async def dub_status_stream(request: Request, job_id: str):
    """SSE progress stream for a job: state snapshots + heartbeat, until
    the job reaches a terminal state or the client disconnects."""
    _require_flag()
    from common_lib.modules.audio_processing.dubbing import pipeline as dp

    async def _gen():
        last = None
        while True:
            if await request.is_disconnected():
                return
            job = dp.get_job(job_id)
            if job is None:
                yield dp.sse_event("error", {"reason": f"job {job_id} not found"})
                return
            snapshot = (job["state"], job["updated_at"])
            if snapshot != last:
                last = snapshot
                yield dp.sse_event("progress", job)
            if job["state"] in ("done", "failed", "aborted"):
                yield dp.sse_event("end", {"state": job["state"]})
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
