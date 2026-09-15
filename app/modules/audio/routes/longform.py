"""Longform (Audiobook + Story) thin routes — VoiceStudio parity Wave 7.

Endpoints:
- ``POST /longform/import`` — import .txt/.md/.epub/.pdf → chapter script
- ``POST /longform/plan`` — parse script → chapter/span plan (preview)
- ``POST /longform/render`` — SSE render job (chapterized m4b/mp3)
- ``POST /longform/preview`` — render single chapter for audition
- ``POST /longform/resume/{job_id}`` — resume interrupted render
- ``GET /longform/jobs`` — list finished renders (library)

All endpoints gated behind ``LONGFORM_ENABLED`` flag (default-OFF).
Pure transport — delegates to ``services.longform_*`` modules.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from common_lib.modules.audio_processing.memory.feature_flags import (
    LONGFORM_ENABLED,
    is_enabled,
)
from common_lib.modules.audio_processing.services.longform_importer import (
    chapterize_plaintext,
    epub_to_chapter_script,
    pdf_to_chapter_script,
)
from common_lib.modules.audio_processing.services.longform_parser import (
    parse_script_to_spans,
)
from common_lib.modules.audio_processing.services.longform_render import (
    LOUDNESS_PRESETS,
    build_concat_list,
    build_ffmetadata,
    build_render_cmd,
    prune_cache_dir,
)
from common_lib.modules.audio_processing.services.longform_resume import (
    build_manifest,
    clear_manifest,
    has_manifest,
    read_manifest,
    scan_resumable,
    work_dir,
    write_manifest,
)
from common_lib.modules.audio_processing.services.tts_service import TTSService
from common_lib.modules.audio_processing.services.longform_render import (
    LOUDNESS_PRESETS as RENDER_LOUDNESS_PRESETS,
    MeasuredLoudness,
    build_loudnorm_apply_filter,
    build_loudnorm_measure_filter,
    parse_loudnorm_measure,
)
from common_lib.modules.audio_processing.editing.ffmpeg_utils import (
    find_ffmpeg,
    run_ffmpeg,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Cover size cap mirrors longform_render's guard (8 MB — a book cover, not a payload).
_COVER_MAX_BYTES = 8 * 1024 * 1024
# Import upload cap — a generous ceiling for a .txt/.md/.epub manuscript that
# still stops a memory-exhaustion upload (the whole file is read into RAM).
_IMPORT_MAX_BYTES = 64 * 1024 * 1024
# Upper bound on chapters in a single /longform/render plan — far above any real
# book, but stops a pathological request from allocating/holding the job forever.
_MAX_CHAPTERS = 10_000

# A cover filename as produced by /longform/cover: 12 hex chars + image ext.
# An exact-match allowlist is the strongest barrier (and the one CodeQL's
# path-injection query recognizes) — anything else is rejected outright.
_COVER_NAME_RE = re.compile(r"^[0-9a-f]{12}\.(?:jpg|jpeg|png)$")


def _safe_cover_path(cover_path: str | None) -> str | None:
    """Confine a user-supplied cover to the upload directory before it can flow
    into ffmpeg. Covers only ever come from ``/longform/cover``, which writes them
    to ``OUTPUTS_DIR/longform_covers`` with a generated name."""
    if not cover_path:
        return None
    from common_lib.modules.audio_processing.projects.config import OUTPUTS_DIR

    name = os.path.basename(cover_path)
    if not _COVER_NAME_RE.match(name):
        return None
    cover_dir = os.path.realpath(os.path.join(OUTPUTS_DIR, "longform_covers"))
    real = os.path.realpath(os.path.join(cover_dir, name))
    if os.path.commonpath([real, cover_dir]) != cover_dir:
        return None
    return real if os.path.isfile(real) else None


class ExpressiveMixin(BaseModel):
    """Optional expressive/quality knobs shared by every longform front door.
    All optional — an omitted field reproduces today's exact render.
    """

    num_step: int | None = Field(default=None, ge=1, le=512)
    guidance_scale: float | None = Field(default=None, ge=0.0, le=20.0)
    position_temperature: float | None = Field(default=None, ge=0.0, le=100.0)
    class_temperature: float | None = Field(default=None, ge=0.0, le=100.0)
    postprocess_output: bool | None = None
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    emo_vector: list[float] | None = Field(default=None, min_length=8, max_length=8)
    emo_text: str | None = Field(default=None, max_length=500)
    emo_alpha: float | None = Field(default=None, ge=0.0, le=1.0)
    vary_repeats: bool = False


def _expressive_opts(req: "ExpressiveMixin"):
    from common_lib.modules.audio_processing.services.audiobook import ExpressiveOptions

    return ExpressiveOptions(
        num_step=req.num_step,
        guidance_scale=req.guidance_scale,
        position_temperature=req.position_temperature,
        class_temperature=req.class_temperature,
        postprocess_output=req.postprocess_output,
        seed=req.seed,
        emo_vector=tuple(req.emo_vector) if req.emo_vector else None,
        emo_text=(req.emo_text or None),
        emo_alpha=req.emo_alpha,
        vary_repeats=bool(req.vary_repeats),
    )


class LongformImportResponse(BaseModel):
    text: str
    chapters: int


@router.post(
    "/longform/import",
    response_model=LongformImportResponse,
    summary="Import manuscript (.txt/.md/.epub/.pdf) into chapter-delimited script",
)
async def longform_import(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Import a manuscript file into a chapter-delimited script.

    EPUB is parsed in spine order (stdlib only, local); PDF text is extracted
    with pypdf (pure-Python) then chapterized; plain text gets ``# `` headings
    inserted ahead of obvious chapter-title lines. Returns the script text + chapter count.
    """
    if not is_enabled(LONGFORM_ENABLED):
        raise HTTPException(
            status_code=404,
            detail="Longform features disabled (LONGFORM_ENABLED flag is OFF)",
        )

    name = (file.filename or "").lower()
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > _IMPORT_MAX_BYTES:
        raise HTTPException(status_code=400, detail="file too large (max 64 MB)")

    try:
        if name.endswith(".epub"):
            script = epub_to_chapter_script(data)
        elif name.endswith(".pdf"):
            script = pdf_to_chapter_script(data)
        else:
            script = chapterize_plaintext(data.decode("utf-8", "ignore"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"couldn't parse file: {e}")

    if not script.strip():
        raise HTTPException(status_code=400, detail="no text found in the file")

    plan = parse_script_to_spans(script)
    return {"text": script, "chapters": len(plan)}


class LongformPlanRequest(BaseModel):
    text: str
    default_voice: str | None = None
    default_speed: float | None = None


@router.post(
    "/longform/plan",
    summary="Parse script into chapter/span plan (preview, no synthesis)",
)
async def longform_plan(req: LongformPlanRequest) -> Dict[str, Any]:
    """Parse a chapter-delimited script into a chapter/span plan. Pure preview, no synthesis."""
    if not is_enabled(LONGFORM_ENABLED):
        raise HTTPException(status_code=404, detail="Longform features disabled")
    plan = parse_script_to_spans(
        req.text, default_voice=req.default_voice, default_speed=req.default_speed
    )
    if not plan:
        raise HTTPException(
            status_code=400, detail="no chapters parsed from the script"
        )
    return {
        "chapters": [
            {
                "title": c["title"],
                "span_count": len(c["spans"]),
                "char_count": sum(len(s["text"]) for s in c["spans"]),
            }
            for c in plan
        ],
        "total_chapters": len(plan),
        "total_spans": sum(len(c["spans"]) for c in plan),
        "total_chars": sum(len(s["text"]) for c in plan for s in c["spans"]),
    }


class LongformCoverResponse(BaseModel):
    path: str


@router.post(
    "/longform/cover",
    response_model=LongformCoverResponse,
    summary="Upload cover image; returns server-side path for render",
)
async def longform_cover(cover: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload a cover image; returns a server-side ``path`` to pass back as ``cover_path``."""
    if not is_enabled(LONGFORM_ENABLED):
        raise HTTPException(status_code=404, detail="Longform features disabled")

    from common_lib.modules.audio_processing.projects.config import OUTPUTS_DIR

    ext = os.path.splitext(cover.filename or "")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png"):
        raise HTTPException(status_code=400, detail="cover must be a .jpg or .png")
    data = await cover.read()
    if not data or len(data) > _COVER_MAX_BYTES:
        raise HTTPException(
            status_code=400, detail="cover must be between 1 byte and 8 MB"
        )
    cover_dir = os.path.join(OUTPUTS_DIR, "longform_covers")
    os.makedirs(cover_dir, exist_ok=True)
    path = os.path.join(cover_dir, f"{uuid.uuid4().hex[:12]}{ext}")
    with open(path, "wb") as f:
        f.write(data)
    return {"path": path}


# ── Expressive options from VoiceStudio (#1208) ──────────────────────────────

LONGFORM_NUM_STEP = 32
LONGFORM_GUIDANCE_SCALE = 2.0


def _omnivoice_sampling_kwargs(opts) -> dict:
    """VoiceStudio-model generate kwargs for the sampling knobs."""
    kw = {
        "num_step": opts.num_step if opts.num_step is not None else LONGFORM_NUM_STEP,
        "guidance_scale": opts.guidance_scale
        if opts.guidance_scale is not None
        else LONGFORM_GUIDANCE_SCALE,
    }
    if opts.position_temperature is not None:
        kw["position_temperature"] = opts.position_temperature
    if opts.class_temperature is not None:
        kw["class_temperature"] = opts.class_temperature
    if opts.postprocess_output is not None:
        kw["postprocess_output"] = opts.postprocess_output
    return kw


def _generic_extra_kwargs(opts) -> dict:
    kw: dict = {}
    if opts.num_step is not None:
        kw["num_step"] = opts.num_step
    if opts.guidance_scale is not None:
        kw["guidance_scale"] = opts.guidance_scale
    if opts.position_temperature is not None:
        kw["position_temperature"] = opts.position_temperature
    if opts.class_temperature is not None:
        kw["class_temperature"] = opts.class_temperature
    if opts.postprocess_output is not None:
        kw["postprocess_output"] = opts.postprocess_output
    if opts.emo_vector:
        kw["emo_vector"] = list(opts.emo_vector)
    if opts.emo_text:
        kw["emo_text"] = opts.emo_text
        kw["use_emo_text"] = True
    if opts.emo_alpha is not None:
        kw["emo_alpha"] = opts.emo_alpha
    return kw


def _segment_seed(base_seed: int, text: str, nonce: int = 0) -> int:
    import zlib

    _NONCE_MIX = 2654435761
    return (
        int(base_seed) + zlib.crc32(text.encode("utf-8")) + int(nonce) * _NONCE_MIX
    ) % (2**31)


def _make_occ_counter(opts):
    state = {"n": 0}

    def next_nonce() -> int:
        if not opts.vary_repeats:
            return 0
        n = state["n"]
        state["n"] = n + 1
        return n

    return next_nonce


class LongformRenderRequest(ExpressiveMixin):
    text: str
    default_voice: str | None = None
    language: str | None = None
    bitrate: str = "128k"
    format: str = "m4b"
    loudness: str | None = None
    cover_path: str | None = None
    metadata: dict | None = None
    lexicon: dict | None = None
    voice_map: dict[str, str] | None = None


def _resolve_default_language(
    language: str | None, default_voice: str | None
) -> str | None:
    if language and language != "Auto":
        return language
    if default_voice:
        from common_lib.modules.audio_processing.projects.config import VOICES_DIR
        from common_lib.modules.audio_processing.core.db import db_conn

        with db_conn() as conn:
            row = conn.execute(
                "SELECT language FROM voice_profiles WHERE id=?", (default_voice,)
            ).fetchone()
        if row:
            try:
                prof_lang = row["language"]
            except (KeyError, IndexError):
                prof_lang = None
            if prof_lang and prof_lang != "Auto":
                return prof_lang
    return None


async def _prepare_synth(
    default_voice: str | None,
    language: str | None = None,
    opts: "ExpressiveOptions" | None = None,
    voice_map: dict | None = None,
):
    from common_lib.modules.audio_processing.services.tts_backend import (
        OmniVoiceBackend,
        active_backend_id,
        get_backend_class,
    )
    from common_lib.modules.audio_processing.services.model_manager import get_model

    opts = opts or ExpressiveOptions()
    cache: dict = {}
    token_cache: dict = {}

    def resolve(voice_id):
        if voice_id not in token_cache:
            token_cache[voice_id] = voice_id  # simplified for now
        key = token_cache[voice_id]
        if key not in cache:
            cache[key] = {
                "ref_audio": None,
                "ref_text": None,
                "instruct": None,
                "seed": None,
            }
        return cache[key]

    engine_id = active_backend_id()
    cls = get_backend_class(engine_id)
    if cls is OmniVoiceBackend:
        model = await get_model()
        sr = getattr(model, "sampling_rate", 24000)
        sampling = _omnivoice_sampling_kwargs(opts)
        next_nonce = _make_occ_counter(opts)

        def synth(text, voice_id, speed=None):
            v = resolve(voice_id)
            seed = _segment_seed(_base_seed(opts, v), text, next_nonce())
            from common_lib.modules.audio_processing.services.tts_backend import (
                generate_with_cached_ref,
            )

            return generate_with_cached_ref(
                model,
                ref_audio=v["ref_audio"],
                ref_text=v["ref_text"],
                text=text,
                language=language,
                instruct=v["instruct"],
                duration=None,
                speed=float(speed) if speed else 1.0,
                **sampling,
            )[0]

        return synth, sr, resolve, engine_id

    backend = cls()
    native_proxy = bool(getattr(cls, "supports_native_omnivoice_controls", False))
    extra = (
        _omnivoice_sampling_kwargs(opts)
        if native_proxy
        else _generic_extra_kwargs(opts)
    )
    next_nonce = _make_occ_counter(opts)

    def synth(text, voice_id, speed=None):
        v = resolve(voice_id)
        seed = _segment_seed(_base_seed(opts, v), text, next_nonce())
        call_extra = dict(extra)
        if native_proxy and seed is not None:
            call_extra["seed"] = seed
        return backend.generate(
            text,
            language=language,
            ref_audio=v["ref_audio"],
            ref_text=v["ref_text"],
            instruct=v["instruct"],
            duration=None,
            speed=float(speed) if speed else 1.0,
            **call_extra,
        )

    return synth, backend.sample_rate, resolve, engine_id


def _base_seed(opts, voice: dict):
    return opts.seed if opts.seed is not None else voice.get("seed")


async def _render_chapter_cached(
    chapter,
    synth,
    sr,
    engine_id,
    resolve,
    cache_dir,
    lexicon=None,
    language=None,
    opts=None,
    voice_map=None,
):
    import json
    import wave
    import torch
    from common_lib.modules.audio_processing.editing.audio_io import atomic_save_wav
    from common_lib.modules.audio_processing.services.longform_render import (
        SegmentCache,
        chapter_cache_key,
    )
    from common_lib.modules.audio_processing.services.pronunciation import (
        apply_lexicon,
        normalize_lexicon,
    )
    from common_lib.modules.audio_processing.services.text_normalization import (
        normalize_for_tts,
    )
    from common_lib.modules.audio_processing.services.watermark import (
        mark_synthetic,
        will_mark,
    )
    from common_lib.modules.audio_processing.services.audiobook import (
        ExpressiveOptions,
        Span,
        voice_map_signature,
    )
    from common_lib.modules.audio_processing.services.chunked_tts import (
        concatenate_audio_chunks,
        join_rendered_chunks,
        split_text_into_chunks,
    )

    opts = opts or ExpressiveOptions()
    spans = [
        Span(
            voice_id=s.voice_id,
            text=normalize_for_tts(s.text, language),
            pause_ms_after=s.pause_ms_after,
            speed=getattr(s, "speed", None),
        )
        for s in chapter.spans
    ]
    spans_tuples = [
        (s.voice_id, s.text, s.pause_ms_after, getattr(s, "speed", None)) for s in spans
    ]
    voice_sigs: dict = {}
    for s in spans:
        k = s.voice_id or ""
        if k not in voice_sigs:
            v = resolve(s.voice_id)
            voice_sigs[k] = (
                f"{v.get('ref_audio')}|{v.get('ref_text')}|{v.get('instruct')}|{v.get('seed')}"
            )
    sig: dict = dict(voice_sigs)
    lex_sig = ""
    if lexicon:
        lex_sig = json.dumps(normalize_lexicon(lexicon), sort_keys=True)
        sig["\x00lexicon"] = lex_sig
    expr_sig = opts.cache_signature()
    if expr_sig:
        sig["\x00expressive"] = expr_sig
    vmap_sig = voice_map_signature(voice_map)
    if vmap_sig:
        sig["\x00voicemap"] = vmap_sig
    seg_extra_sig = f"{lex_sig}\x00{expr_sig}" if expr_sig else lex_sig
    if vmap_sig:
        seg_extra_sig = f"{seg_extra_sig}\x00{vmap_sig}"
    if will_mark():
        sig["\x00watermark"] = "1"
    key = chapter_cache_key(
        spans_tuples, sample_rate=sr, engine_id=engine_id, voice_sig=sig
    )
    wav_path = os.path.join(cache_dir, f"{key}.wav")

    if os.path.exists(wav_path):
        try:
            with wave.open(wav_path, "rb") as w:
                dur = w.getnframes() / float(w.getframerate() or sr)
            return wav_path, dur, True, None
        except Exception:
            pass

    seg_cache = SegmentCache(
        cache_dir,
        sample_rate=sr,
        engine_id=engine_id,
        voice_sig=voice_sigs,
        extra_sig=seg_extra_sig,
        vary_repeats=opts.vary_repeats,
    )
    from common_lib.modules.audio_processing.services.audiobook import (
        synthesize_chapter,
    )

    audio, dur = synthesize_chapter(
        spans, synth, sr, lexicon=lexicon, segment_cache=seg_cache
    )
    audio = mark_synthetic(audio, sr, context="longform.chapter")
    atomic_save_wav(wav_path, audio, sr)
    return (
        wav_path,
        dur,
        False,
        {"total": seg_cache.hits + seg_cache.misses, "cached": seg_cache.hits},
    )


async def _render_longform_sse(
    plan,
    *,
    default_voice: str | None,
    language: str | None = None,
    fmt: str = "m4b",
    bitrate: str = "128k",
    loudness: str | None = None,
    cover_path: str | None = None,
    metadata: dict | None = None,
    lexicon: dict | None = None,
    opts: "ExpressiveOptions" | None = None,
    voice_map: dict | None = None,
    job_type: str = "longform",
    job_id: str | None = None,
    resume: bool = False,
    is_disconnected: Callable[[], Awaitable[bool]] | None = None,
):
    from common_lib.modules.audio_processing.projects.config import OUTPUTS_DIR
    from common_lib.modules.audio_processing.core.failure import (
        build_failure,
        build_failure_event,
    )
    from common_lib.modules.audio_processing.services import gpu_gateway

    opts = opts or ExpressiveOptions()
    job_id = re.sub(r"[^A-Za-z0-9_-]", "", job_id or "")[:64] or uuid.uuid4().hex[:16]
    try:
        from common_lib.modules.audio_processing.core import job_store

        if not resume:
            job_store.create(job_id, type=job_type)
        job_store.mark_running(job_id)
    except Exception:
        job_store = None

    try:
        title = (metadata or {}).get("title") or (
            plan.chapters[0].title if plan.chapters else ""
        )
        write_manifest(
            build_manifest(
                job_id=job_id,
                job_type=job_type,
                title=title,
                plan_chapters=[
                    {"title": c.title, "spans": [s.to_dict() for s in c.spans]}
                    for c in plan.chapters
                ],
                params={
                    "default_voice": default_voice,
                    "language": language,
                    "fmt": fmt,
                    "bitrate": bitrate,
                    "loudness": loudness,
                    "cover_path": cover_path,
                    "metadata": metadata,
                    "lexicon": lexicon,
                    "expressive": opts.to_manifest(),
                    "voice_map": voice_map,
                },
            )
        )
    except Exception:
        logger.debug("[%s] resume manifest write skipped", job_id, exc_info=True)

    def _emit(payload: dict) -> str:
        if job_store is not None:
            try:
                job_store.append_event(job_id, json.dumps(payload))
            except Exception:
                pass
        return f"data: {json.dumps(payload)}\n\n"

    if not plan.chapters:
        yield _emit({"type": "error", "error": "nothing to render (no chapters)"})
        return
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        yield _emit(
            {"type": "error", "error": "ffmpeg not available; the output needs it"}
        )
        return

    work = work_dir(job_type, job_id)
    if work is None:
        yield _emit({"type": "error", "error": "invalid job id"})
        return
    os.makedirs(work, exist_ok=True)
    cache_dir = os.path.join(OUTPUTS_DIR, "longform_cache")
    os.makedirs(cache_dir, exist_ok=True)
    prune_cache_dir(cache_dir)

    try:
        resolved_lang = _resolve_default_language(language, default_voice)
        operation = "audiobook" if job_type == "audiobook" else "longform"
        decision = gpu_gateway.decide(operation)
        chapter_run = gpu_gateway.JobRun(operation)

        total = len(plan.chapters)
        chapter_files: list[str] = []
        chapters_meta: list[tuple[str, int]] = []
        cached_n = 0
        failed: list[int] = []
        last_chapter_exc: Exception | None = None
        interrupted = False
        yield _emit({"type": "started", "job_id": job_id, "chapters": total})

        synth, sr, resolve, engine_id = await _prepare_synth(
            default_voice, resolved_lang, opts, voice_map
        )

        for i, chapter in enumerate(plan.chapters):
            if is_disconnected is not None:
                try:
                    gone = await is_disconnected()
                except Exception:
                    gone = False
                if gone:
                    interrupted = True
                    break
            try:
                wav_path, dur, was_cached, seg_stats = await _render_chapter_cached(
                    chapter,
                    synth,
                    sr,
                    engine_id,
                    resolve,
                    cache_dir,
                    lexicon,
                    resolved_lang,
                    opts,
                    voice_map,
                )
            except Exception as e:
                logger.warning(
                    "[%s] chapter %d (%s) failed to render",
                    job_id,
                    i,
                    chapter.title,
                    exc_info=True,
                )
                failed.append(i)
                last_chapter_exc = e
                yield _emit(
                    {
                        "type": "chapter_error",
                        "index": i,
                        "total": total,
                        "title": chapter.title,
                        **build_failure(
                            e, stage="longform_chapter", include_diagnostic=False
                        ),
                    }
                )
                continue
            chapter_files.append(wav_path)
            chapters_meta.append((chapter.title, int(round(dur * 1000))))
            cached_n += 1 if was_cached else 0
            ev = {
                "type": "chapter",
                "index": i,
                "total": total,
                "title": chapter.title,
                "duration_s": round(dur, 2),
                "cached": was_cached,
            }
            if seg_stats is not None:
                ev["segments"] = seg_stats["total"]
                ev["cached_segments"] = seg_stats["cached"]
            yield _emit(ev)

        route_notice = chapter_run.notice()
        if route_notice is not None:
            yield _emit(
                {
                    "type": "routing_notice",
                    "status": route_notice[0],
                    "reason": route_notice[1],
                }
            )

        if interrupted:
            if job_store is not None:
                try:
                    job_store.mark_cancelled(job_id)
                except Exception:
                    pass
            yield _emit(
                {
                    "type": "stopped",
                    "rendered": len(chapter_files),
                    "total": total,
                    "cached_chapters": cached_n,
                    "failed_chapters": failed,
                }
            )
            return

        if not chapter_files:
            if last_chapter_exc is not None:
                ev = build_failure_event(last_chapter_exc, stage="longform_render")
                ev["reason"] = f"all {total} chapters failed to render — {ev['reason']}"
                ev["error"] = ev["reason"]
            else:
                ev = {
                    "type": "error",
                    "error": "all chapters failed to render",
                    "reason": "all chapters failed to render",
                }
            if job_store is not None:
                try:
                    job_store.mark_failed(job_id, ev["reason"])
                except Exception:
                    pass
            yield _emit(ev)
            return

        yield _emit({"type": "assembling"})
        meta_path = os.path.join(work, "chapters.ffmeta")
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(build_ffmetadata(chapters_meta, global_meta=metadata))
        concat_path = os.path.join(work, "concat.txt")
        with open(concat_path, "w", encoding="utf-8") as f:
            f.write(build_concat_list(chapter_files))
        ext = "mp3" if (fmt or "").lower() == "mp3" else "m4b"
        out_name = f"{job_type}_{job_id}.{ext}"
        out_path = os.path.join(OUTPUTS_DIR, out_name)

        # Two-pass loudness
        measured = None
        if loudness and loudness.lower() in RENDER_LOUDNESS_PRESETS:
            measure_filt = build_loudnorm_measure_filter(loudness)
            if measure_filt:
                measure_cmd = build_loudnorm_measure_cmd(
                    ffmpeg, concat_path, measure_filt
                )
                try:
                    res = run_ffmpeg(measure_cmd, timeout=300)
                    measured = parse_loudnorm_measure(res.stderr)
                except Exception:
                    measured = None

        apply_filt = (
            build_loudnorm_apply_filter(loudness, measured)
            if measured is not None
            else build_loudnorm_filter(loudness)
        )
        render_cmd = build_render_cmd(
            ffmpeg,
            concat_path,
            meta_path,
            out_path,
            fmt=fmt,
            bitrate=bitrate,
            cover_path=cover_path,
            loudness=loudness,
            measured=measured,
        )
        run_ffmpeg(render_cmd, timeout=300)

        if job_store is not None:
            try:
                job_store.mark_done(
                    job_id,
                    {
                        "output": out_name,
                        "duration_s": sum(d for _, d in chapters_meta) / 1000.0,
                        "chapters": total,
                        "title": title,
                    },
                )
            except Exception:
                pass
        clear_manifest(job_type, job_id)
        yield _emit(
            {
                "type": "done",
                "job_id": job_id,
                "output": out_name,
                "duration_s": round(sum(d for _, d in chapters_meta) / 1000.0, 2),
                "chapters": total,
                "cached_chapters": cached_n,
                "title": title,
            }
        )

    except Exception as e:
        logger.exception("[%s] render failed", job_id)
        if job_store is not None:
            try:
                job_store.mark_failed(job_id, str(e))
            except Exception:
                pass
        yield _emit({"type": "error", "error": str(e)})


@router.post("/longform/render")
async def longform_render(
    req: LongformRenderRequest, request: Request
) -> StreamingResponse:
    """SSE render job: chapterized m4b/mp3 with progress events."""
    if not is_enabled(LONGFORM_ENABLED):
        raise HTTPException(status_code=404, detail="Longform features disabled")
    plan_chapters = parse_script_to_spans(req.text, default_voice=req.default_voice)
    if not plan_chapters:
        raise HTTPException(
            status_code=400, detail="no chapters parsed from the script"
        )
    if len(plan_chapters) > _MAX_CHAPTERS:
        raise HTTPException(
            status_code=400, detail=f"too many chapters (max {_MAX_CHAPTERS})"
        )

    from common_lib.modules.audio_processing.services.audiobook import (
        AudiobookPlan,
        Chapter,
        Span,
    )

    plan = AudiobookPlan(
        chapters=[
            Chapter(title=c["title"], spans=[Span(**s) for s in c["spans"]])
            for c in plan_chapters
        ]
    )

    cover = _safe_cover_path(req.cover_path)
    opts = _expressive_opts(req)
    job_id = uuid.uuid4().hex[:16]

    async def event_gen():
        async for evt in _render_longform_sse(
            plan,
            default_voice=req.default_voice,
            language=req.language,
            fmt=req.format,
            bitrate=req.bitrate,
            loudness=req.loudness,
            cover_path=cover,
            metadata=req.metadata,
            lexicon=req.lexicon,
            opts=opts,
            voice_map=req.voice_map,
            job_type="longform",
            job_id=job_id,
            resume=False,
            is_disconnected=lambda: request.is_disconnected(),
        ):
            yield evt

    return StreamingResponse(event_gen(), media_type="text/event-stream")


class LongformPreviewRequest(ExpressiveMixin):
    text: str
    chapter_index: int = 0
    default_voice: str | None = None
    language: str | None = None
    lexicon: dict | None = None
    voice_map: dict[str, str] | None = None


@router.post("/longform/preview")
async def longform_preview(req: LongformPreviewRequest) -> Dict[str, Any]:
    """Render a single chapter for audition. Warms the shared cache."""
    if not is_enabled(LONGFORM_ENABLED):
        raise HTTPException(status_code=404, detail="Longform features disabled")
    from common_lib.modules.audio_processing.projects.config import OUTPUTS_DIR
    from common_lib.modules.audio_processing.services.audiobook import (
        AudiobookPlan,
        Chapter,
        Span,
    )
    from common_lib.modules.audio_processing.services import gpu_gateway

    plan_chapters = parse_script_to_spans(req.text, default_voice=req.default_voice)
    if not plan_chapters:
        raise HTTPException(status_code=400, detail="no chapters parsed")
    n = len(plan_chapters)
    if not (0 <= req.chapter_index < n):
        raise HTTPException(
            status_code=400, detail=f"chapter_index out of range (0..{n - 1})"
        )

    plan = AudiobookPlan(
        chapters=[
            Chapter(title=c["title"], spans=[Span(**s) for s in c["spans"]])
            for c in plan_chapters
        ]
    )
    chapter = plan.chapters[req.chapter_index]
    cache_dir = os.path.join(OUTPUTS_DIR, "longform_cache")
    os.makedirs(cache_dir, exist_ok=True)
    resolved_lang = _resolve_default_language(req.language, req.default_voice)
    opts = _expressive_opts(req)
    decision = gpu_gateway.decide("longform")

    synth, sr, resolve, engine_id = await _prepare_synth(
        req.default_voice, resolved_lang, opts, req.voice_map
    )
    wav_path, dur, was_cached, _ = await _render_chapter_cached(
        chapter,
        synth,
        sr,
        engine_id,
        resolve,
        cache_dir,
        req.lexicon,
        resolved_lang,
        opts,
        req.voice_map,
    )
    return {
        "output": os.path.relpath(wav_path, OUTPUTS_DIR),
        "duration_s": round(dur, 2),
        "cached": was_cached,
        "title": chapter.title,
    }


@router.post("/longform/resume/{job_id}")
async def longform_resume(job_id: str, request: Request) -> StreamingResponse:
    """Resume an interrupted longform render from its manifest."""
    if not is_enabled(LONGFORM_ENABLED):
        raise HTTPException(status_code=404, detail="Longform features disabled")
    manifest = read_manifest("longform", job_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="no resumable manifest found")

    params = manifest.get("params", {})
    plan_chapters = manifest.get("plan", [])
    if not plan_chapters:
        raise HTTPException(status_code=400, detail="manifest has no plan")

    from common_lib.modules.audio_processing.services.audiobook import (
        AudiobookPlan,
        Chapter,
        Span,
        ExpressiveOptions,
    )

    plan = AudiobookPlan(
        chapters=[
            Chapter(title=c["title"], spans=[Span(**s) for s in c["spans"]])
            for c in plan_chapters
        ]
    )

    cover = _safe_cover_path(params.get("cover_path"))
    opts = ExpressiveOptions.from_manifest(params.get("expressive"))
    voice_map = params.get("voice_map")

    async def event_gen():
        async for evt in _render_longform_sse(
            plan,
            default_voice=params.get("default_voice"),
            language=params.get("language"),
            fmt=params.get("fmt", "m4b"),
            bitrate=params.get("bitrate", "128k"),
            loudness=params.get("loudness"),
            cover_path=cover,
            metadata=params.get("metadata"),
            lexicon=params.get("lexicon"),
            opts=opts,
            voice_map=voice_map,
            job_type="longform",
            job_id=job_id,
            resume=True,
            is_disconnected=lambda: request.is_disconnected(),
        ):
            yield evt

    return StreamingResponse(event_gen(), media_type="text/event-stream")


class LongformJobItem(BaseModel):
    job_id: str
    type: str
    output: str
    duration_s: float
    chapters: int
    created_at: str | None = None
    title: str | None = None


@router.get("/longform/jobs", response_model=List[LongformJobItem])
async def longform_jobs(limit: int = Query(50, ge=1, le=500)) -> List[Dict[str, Any]]:
    """Finished longform renders, newest-first, ready to re-download."""
    if not is_enabled(LONGFORM_ENABLED):
        raise HTTPException(status_code=404, detail="Longform features disabled")
    jobs = []
    for item in scan_resumable():
        if len(jobs) >= limit:
            break
        manifest = load_manifest_file(item["manifest_path"])
        if not manifest:
            continue
        # Note: scan_resumable finds jobs with manifests, but finished jobs
        # have their manifest cleared. We check job_store for done jobs.
        try:
            from common_lib.modules.audio_processing.core import job_store

            job = job_store.get_job(item["job_id"])
            if job and job.get("status") == "done":
                events = job_store.events_since(item["job_id"])
                # Find done event
                done_event = None
                for ev in reversed(events or []):
                    raw = ev.get("payload") if isinstance(ev, dict) else None
                    if raw:
                        try:
                            obj = json.loads(raw)
                            if obj.get("type") == "done":
                                done_event = obj
                                break
                        except (ValueError, TypeError):
                            continue
                if done_event:
                    jobs.append(
                        {
                            "job_id": item["job_id"],
                            "type": item["job_type"],
                            "output": done_event.get("output"),
                            "duration_s": round(done_event.get("duration_s", 0), 2),
                            "chapters": done_event.get("chapters", 0),
                            "created_at": job.get("created_at"),
                            "title": done_event.get("title"),
                        }
                    )
        except Exception:
            continue
    return jobs


__all__ = ["router"]
