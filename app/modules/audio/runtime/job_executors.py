"""Audio background-job executors.

Moves blocking audio work OFF the FastAPI event loop onto the shared jobs
module: every executor is a blocking ``fn(record, check_cancel, report_progress)``
registered via :func:`ensure_audio_executors_registered` and runs on a jobs
worker thread under the jobs per-device semaphore (gpu: 1, cpu: 4).

Contract notes (keep in sync with ``vision/runtime/job_executors.py``):

* Kind names are namespaced (``audio.<area>.<op>``) so the generic
  ``GET /api/v1/jobs?kind=`` filter and prefix filtering stay unambiguous.
* Jobs params arrive as the decoded dict from ``record.get_params()`` — never
  as the raw JSON string on ``record.params``.
* ``report_progress`` takes a **percentage float** (0-100), not a dict.
* Async ``AudioService`` methods are bridged with ``asyncio.run`` on the worker
  thread (see ``_run_async``); no coroutine is ever awaited inline here.
* Artifacts are refs only: audio/metadata bytes are persisted through
  ``common_lib.modules.jobs.artifacts.save_artifact`` under
  ``GENERATED_CONTENT/jobs/<job_id>/`` and never inlined into ``JobRecord``.
* ``sync_<...>`` helpers below are the single implementation of each job; the
  route handler keeps its own inline path only for ``sync=true`` requests.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Callable, Iterator, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Job kinds — namespaced ``audio.*``
# ---------------------------------------------------------------------------

#: Prefix shared by every audio job kind (used by ``GET /api/v1/audio/jobs``).
AUDIO_KIND_PREFIX = "audio."

# Core speech / music
TTS_KIND = "audio.tts"
SPEAK_KIND = "audio.speak"
TRANSCRIBE_KIND = "audio.transcribe"
VOICE_CLONE_KIND = "audio.voice_clone"
SINGING_KIND = "audio.singing"
MUSIC_KIND = "audio.music"
SFX_KIND = "audio.sfx"
ADVANCED_TTS_KIND = "audio.advanced_tts"

# Processing / editing
EDIT_KIND = "audio.edit"
STEMS_KIND = "audio.stems"
ANALYZE_KIND = "audio.analyze"
MASTERING_KIND = "audio.mastering"
RESTORATION_KIND = "audio.restoration"
TIME_PITCH_KIND = "audio.time_pitch"
ARRANGEMENT_KIND = "audio.arrangement"

# Speech-to-speech
STS_CONVERT_KIND = "audio.sts.convert"
STS_ACCENT_KIND = "audio.sts.accent"
STS_EMOTION_KIND = "audio.sts.emotion"

# Long-form / full song / orchestra
FULL_SONG_KIND = "audio.full_song"
ORCHESTRA_KIND = "audio.orchestra"
LONGFORM_PREVIEW_KIND = "audio.longform.preview"

# YuE music generation
YUE_GENERATE_KIND = "audio.yue.generate"
YUE_PLAN_KIND = "audio.yue.plan"
YUE_COVER_KIND = "audio.yue.cover"
YUE_EDIT_KIND = "audio.yue.edit"

# IO / DSP
EXPORT_BATCH_KIND = "audio.export.batch"
IMPORT_BATCH_KIND = "audio.import.batch"
EFFECTS_CHAIN_KIND = "audio.effects.chain"

# Dubbing
DUB_CLONE_KIND = "audio.dub.clone"
DUB_INGEST_KIND = "audio.dub.ingest_url"

# Device classes / timeouts (single source of truth).
GPU = "gpu"
CPU = "cpu"
TIMEOUT_GPU = 1800.0
TIMEOUT_GPU_LONG = 3600.0  # YuE songs / full pipeline runs
TIMEOUT_CPU = 600.0

# Keys that carry inline payloads — always stripped before persisting metadata.
_B64_KEYS: tuple[str, ...] = (
    "audio_base64",
    "audio_b64",
    "reference_audio_b64",
    "source_audio_b64",
    "target_voice_b64",
    "image_b64",
    "image",
    "mask_b64",
)
_AUDIO_SUFFIXES: tuple[str, ...] = (
    ".wav",
    ".mp3",
    ".flac",
    ".ogg",
    ".m4a",
    ".aac",
    ".opus",
)
_META_SUFFIXES: tuple[str, ...] = (".json", ".abc", ".mid", ".midi", ".txt")


# ---------------------------------------------------------------------------
# Record / payload helpers
# ---------------------------------------------------------------------------


def _record_params(record: Any) -> dict[str, Any]:
    """Decode the job params dict (never touches the raw ``record.params``)."""
    try:
        params: Any = record.get_params()
    except Exception:  # noqa: BLE001 - defensive: records must never crash a job
        return {}
    return params if isinstance(params, dict) else {}


def _record_id(record: Any) -> str:
    """Return the job id from a record."""
    try:
        job_id: Any = record.id
    except Exception:  # noqa: BLE001
        return "unknown"
    return str(job_id)


def _strip_b64(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of payload without inline (base64) blobs."""
    return {k: v for k, v in payload.items() if k not in _B64_KEYS}


def _to_dict(value: Any) -> dict[str, Any]:
    """Coerce a pydantic model (or mapping) into a plain dict."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    for attr in ("model_dump", "dict"):
        dump = getattr(value, attr, None)
        if callable(dump):
            try:
                dumped: Any = dump()
                if isinstance(dumped, dict):
                    return dumped
            except Exception:  # noqa: BLE001
                continue
    if hasattr(value, "__dict__"):
        return {k: v for k, v in vars(value).items() if not k.startswith("_")}
    return {"result": str(value)}


def _cancelled_result() -> dict[str, Any]:
    """Standard payload for a cooperatively cancelled executor."""
    return {"result_refs": [], "status": "cancelled"}


def _run_async(coro_factory: Callable[[], Any]) -> Any:
    """Run an async service coroutine to completion on this worker thread.

    The jobs worker already owns a private thread, so a private event loop via
    ``asyncio.run`` is safe and keeps the FastAPI loop untouched. A factory is
    taken (not a coroutine) so a cancelled job never leaves one un-awaited.
    """
    return asyncio.run(coro_factory())


# ---------------------------------------------------------------------------
# Artifact helpers
# ---------------------------------------------------------------------------


def _save_json(job_id: str, filename: str, payload: dict[str, Any]) -> str:
    """Persist a JSON-serializable metadata payload, returning its ref."""
    from common_lib.modules.jobs.artifacts import save_artifact

    return save_artifact(
        job_id, filename, json.dumps(payload, default=str).encode("utf-8")
    )


def _iter_paths(node: Any) -> Iterator[str]:
    """Yield every string leaf of a nested payload."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _iter_paths(value)
    elif isinstance(node, (list, tuple, set)):
        for value in node:
            yield from _iter_paths(value)


def _collect_file_refs(job_id: str, payload: Any) -> list[str]:
    """Copy existing audio/metadata files referenced by payload into the job dir.

    Batch/stem responses return lists of output paths; rather than encode that
    shape per endpoint, every existing path with a known suffix is copied and
    referenced. Paths that do not exist (URLs, virtual paths) are skipped.
    """
    from common_lib.modules.jobs.artifacts import save_artifact

    refs: list[str] = []
    seen: set[str] = set()
    known: tuple[str, ...] = _AUDIO_SUFFIXES + _META_SUFFIXES
    for path in _iter_paths(payload):
        if path in seen or not path:
            continue
        if os.path.splitext(path)[1].lower() not in known:
            continue
        if not os.path.isfile(path):
            continue
        seen.add(path)
        try:
            with open(path, "rb") as handle:
                data: bytes = handle.read()
        except OSError as exc:
            logger.warning("jobs: could not read artifact %s: %s", path, exc)
            continue
        try:
            refs.append(save_artifact(job_id, os.path.basename(path), data))
        except Exception as exc:  # noqa: BLE001
            logger.warning("jobs: could not persist artifact %s: %s", path, exc)
    return refs


def _output_dir_file(filename: Any) -> Optional[str]:
    """Return the on-disk path of a file the service wrote to ``output_dir``."""
    name: str = str(filename or "").strip()
    if not name:
        return None
    try:
        candidate: str = os.path.join(str(_audio_service().output_dir), name)
    except Exception:  # noqa: BLE001
        return None
    return candidate if os.path.isfile(candidate) else None


def _finish(
    job_id: str,
    payload: dict[str, Any],
    *,
    status: str = "success",
    extra_files: tuple[Any, ...] = (),
) -> dict[str, Any]:
    """Persist a result payload: artifact files first, then ``result.json``."""
    refs: list[str] = []
    for candidate in extra_files:
        ref: Optional[str] = _output_dir_file(candidate)
        if ref:
            refs.append(ref)
    refs.extend(_collect_file_refs(job_id, payload))
    deduped: list[str] = list(dict.fromkeys(refs))
    meta: dict[str, Any] = _strip_b64(payload)
    meta["artifact_files"] = deduped
    deduped.append(_save_json(job_id, "result.json", meta))
    return {"result_refs": deduped, "status": status}


# ---------------------------------------------------------------------------
# AudioService bridge
# ---------------------------------------------------------------------------


def _audio_service() -> Any:
    """Return the ``AudioService`` singleton (its constructor is sync).

    Indirected through this helper so tests can substitute a stub service
    without constructing the real (torch-scale) ``AudioService``.
    """
    from common_lib.modules.audio_processing.service import get_audio_service

    return get_audio_service()


def _build_request(request_cls: str, params: dict[str, Any]) -> Any:
    """Rehydrate a request schema from the jobs params dict."""
    from common_lib.modules.audio_processing import schemas

    cls: Any = getattr(schemas, request_cls, None)
    if cls is None:
        raise ValueError(f"Unknown audio request schema: {request_cls!r}")
    return cls(**params)


def _service_executor(method: str, request_cls: str) -> Callable[..., Any]:
    """Build an executor running ``AudioService.<method>(<RequestCls>(**params))``.

    Every core audio endpoint follows the same shape: rehydrate the request,
    call the async service method on this worker thread, copy produced files
    into the job artifact dir, persist metadata.
    """

    def executor(
        record: Any,
        check_cancel: Callable[[], bool],
        report_progress: Callable[[float], None],
    ) -> Any:
        job_id: str = _record_id(record)
        params: dict[str, Any] = _record_params(record)
        request: Any = _build_request(request_cls, params)
        report_progress(10.0)
        if check_cancel():
            return _cancelled_result()
        service: Any = _audio_service()
        result: Any = _run_async(lambda: getattr(service, method)(request))
        if check_cancel():
            return _cancelled_result()
        report_progress(90.0)
        payload: dict[str, Any] = _to_dict(result)
        out: dict[str, Any] = _finish(
            job_id,
            payload,
            extra_files=(payload.get("filename"), payload.get("path")),
        )
        report_progress(100.0)
        return out

    executor.__name__ = f"{method}_executor"
    executor.__doc__ = f"Blocking executor for the audio ``{method}`` job."
    return executor


# ---------------------------------------------------------------------------
# Core speech / music
# ---------------------------------------------------------------------------

tts_executor = _service_executor("generate_tts", "TTSRequest")
speak_executor = _service_executor("generate_speak", "SpeakRequest")
transcribe_executor = _service_executor("transcribe", "TranscriptionRequest")
voice_clone_executor = _service_executor("clone_voice", "VoiceCloningRequest")
singing_executor = _service_executor("synthesize_singing", "SingingRequest")
music_executor = _service_executor("generate_music", "MusicGenRequest")
sfx_executor = _service_executor("generate_sfx", "SFXRequest")
full_song_executor = _service_executor("generate_full_song", "FullSongGenRequest")
orchestra_executor = _service_executor("compose_orchestra", "OrchestraRequest")

# ---------------------------------------------------------------------------
# Processing / editing
# ---------------------------------------------------------------------------

edit_executor = _service_executor("edit_audio", "AudioEditRequest")
stems_executor = _service_executor("separate_stems", "StemSeparationRequest")
mastering_executor = _service_executor("master_audio", "MasteringRequest")
restoration_executor = _service_executor("restore_audio", "RestorationRequest")
time_pitch_executor = _service_executor("time_pitch_audio", "TimePitchRequest")
arrangement_executor = _service_executor("plan_arrangement", "ArrangementRequest")


def analyze_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.analyze`` (tempo/key/loudness analysis)."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    audio_path: str = str(params.get("audio_path", ""))
    if not audio_path:
        raise ValueError("Missing required 'audio_path' param")
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()
    service: Any = _audio_service()
    result: Any = _run_async(lambda: service.analyze_audio(audio_path))
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)
    out: dict[str, Any] = _finish(job_id, _to_dict(result))
    report_progress(100.0)
    return out


# ---------------------------------------------------------------------------
# Advanced TTS (sync engine)
# ---------------------------------------------------------------------------


def advanced_tts_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.advanced_tts`` (emotion/SSML/multi-speaker)."""
    from common_lib.modules.audio_processing.generation.tts.advanced import (
        AdvancedTTSConfig,
        AdvancedTTSEngine,
        SpeakerConfig,
    )
    from common_lib.modules.audio_processing.schemas import AdvancedTTSRequest

    job_id: str = _record_id(record)
    request: Any = AdvancedTTSRequest(**_record_params(record))
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    filename: str = f"advanced_tts_{job_id}.wav"
    output_path: str = os.path.join(str(_audio_service().output_dir), filename)

    speakers = None
    if request.speakers:
        speakers = [
            SpeakerConfig(
                speaker_id=s.get("speaker_id", f"speaker_{i}"),
                voice_description=s.get("voice_description", "A natural clear voice"),
                emotion=s.get("emotion", "neutral"),
                speed=s.get("speed", 1.0),
                pitch_shift=s.get("pitch_shift", 0.0),
                energy=s.get("energy", 0.7),
            )
            for i, s in enumerate(request.speakers)
        ]

    config = AdvancedTTSConfig(
        text=request.text,
        ssml=request.ssml,
        model_id=request.model_id,
        description=request.description,
        emotion=request.emotion,
        speed=request.speed,
        pitch_shift=request.pitch_shift,
        energy=request.energy,
        brightness=request.brightness,
        speakers=speakers,
        pronunciation_guide=request.pronunciation_guide,
        reverb_amount=request.reverb_amount,
        eq_enabled=request.eq_enabled,
        compression_enabled=request.compression_enabled,
        word_timestamps=request.word_timestamps,
        output_format=request.output_format,
        sample_rate=24000,
        seed=request.seed,
        language=request.language,
        reference_audio_path=request.reference_audio_path,
    )

    report_progress(30.0)
    result: dict[str, Any] = dict(AdvancedTTSEngine().synthesize(config, output_path))
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    payload: dict[str, Any] = {
        "audio_url": f"/generated/audio/{filename}",
        "filename": filename,
        "duration_seconds": result.get("duration"),
        "method": result.get("method", "unknown"),
        "emotion": result.get("emotion"),
        "emotion_params": result.get("emotion_params"),
        "word_timestamps": result.get("word_timestamps"),
        "pronunciation_data": result.get("pronunciation_data"),
        "ssml_segments": result.get("ssml_segments"),
        "metadata": result,
    }
    out: dict[str, Any] = _finish(job_id, payload, extra_files=(filename,))
    report_progress(100.0)
    return out


# ---------------------------------------------------------------------------
# Speech-to-speech (sync engine)
# ---------------------------------------------------------------------------


def _speech_to_speech(
    record: Any,
    params: dict[str, Any],
    *,
    mode: str,
) -> dict[str, Any]:
    """Shared STS body for the convert / accent / emotion executors."""
    from common_lib.modules.audio_processing.generation.speech_to_speech.converter import (
        ConversionConfig,
        SpeechToSpeechEngine,
    )

    job_id: str = _record_id(record)
    engine = SpeechToSpeechEngine()
    filename: str = f"sts_{mode}_{job_id}.wav"
    output_path: str = os.path.join(str(_audio_service().output_dir), filename)

    if mode == "accent_transfer":
        config = ConversionConfig(
            source_audio_path=params.get("audio_path"),
            source_accent=params.get("source_accent"),
            target_accent=params.get("target_accent"),
            accent_strength=params.get("strength", 0.8),
            mode=mode,
        )
        result: dict[str, Any] = engine.transfer_accent(config, output_path)
        method: str = "accent_transfer"
    elif mode == "emotion_transfer":
        config = ConversionConfig(
            source_audio_path=params.get("audio_path"),
            source_emotion=params.get("source_emotion"),
            target_emotion=params.get("target_emotion"),
            emotion_strength=params.get("strength", 0.8),
            mode=mode,
        )
        result = engine.transfer_emotion(config, output_path)
        method = "emotion_transfer"
    else:
        config = ConversionConfig(
            source_audio_path=params.get("source_audio_path"),
            target_voice_path=params.get("target_voice_path"),
            mode=params.get("mode", "voice_conversion"),
            f0_up_key=params.get("f0_up_key", 0),
            index_rate=params.get("index_rate", 0.75),
            filter_radius=params.get("filter_radius", 3),
            rms_mix_rate=params.get("rms_mix_rate", 0.25),
            protect=params.get("protect", 0.33),
            source_accent=params.get("source_accent"),
            target_accent=params.get("target_accent"),
            accent_strength=params.get("accent_strength", 0.8),
            source_emotion=params.get("source_emotion"),
            target_emotion=params.get("target_emotion"),
            emotion_strength=params.get("emotion_strength", 0.8),
            output_format=params.get("output_format", "wav"),
            sample_rate=params.get("sample_rate", 44100),
        )
        requested_mode: str = str(params.get("mode", "voice_conversion"))
        if requested_mode == "accent_transfer":
            result = engine.transfer_accent(config, output_path)
            method = "accent_transfer"
        elif requested_mode == "emotion_transfer":
            result = engine.transfer_emotion(config, output_path)
            method = "emotion_transfer"
        else:
            result = engine.convert_voice(config, output_path)
            method = "voice_conversion"

    payload: dict[str, Any] = {
        "audio_url": f"/generated/audio/{filename}",
        "filename": filename,
        "duration_seconds": result.get("duration_seconds"),
        "method": result.get("method", method),
        "similarity_score": result.get("similarity_score"),
        "metadata": result,
    }
    return _finish(job_id, payload, extra_files=(filename,))


def sts_convert_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.sts.convert`` (voice/accent/emotion mode)."""
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()
    out: dict[str, Any] = _speech_to_speech(record, params, mode="convert")
    report_progress(100.0)
    return out


def sts_accent_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.sts.accent`` (quick accent transfer)."""
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()
    out: dict[str, Any] = _speech_to_speech(record, params, mode="accent_transfer")
    report_progress(100.0)
    return out


def sts_emotion_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.sts.emotion`` (quick emotion transfer)."""
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()
    out: dict[str, Any] = _speech_to_speech(record, params, mode="emotion_transfer")
    report_progress(100.0)
    return out


# ---------------------------------------------------------------------------
# YuE music generation (sync generator)
# ---------------------------------------------------------------------------


def _yue_generator() -> Any:
    from common_lib.modules.audio_processing.generation.music.yue import YuEGenerator

    return YuEGenerator()


def yue_generate_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.yue.generate`` (full song, GPU-heavy)."""
    from common_lib.modules.audio_processing.schemas.yue import YuESongRequest

    job_id: str = _record_id(record)
    req: Any = YuESongRequest(**_record_params(record))
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()
    report_progress(15.0)
    result: Any = _yue_generator().generate(
        style=req.style,
        lyrics=req.lyrics,
        cot=req.cot,
        seed=req.seed,
        abc=req.abc,
        output_path=f"outputs/{req.id}.{req.output_format}",
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)
    out: dict[str, Any] = _finish(job_id, _to_dict(result))
    report_progress(100.0)
    return out


def yue_plan_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.yue.plan`` (symbolic ABC plan)."""
    from common_lib.modules.audio_processing.schemas.yue import YuESongRequest

    job_id: str = _record_id(record)
    req: Any = YuESongRequest(**_record_params(record))
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()
    result: Any = _yue_generator().plan(
        style=req.style,
        lyrics=req.lyrics,
        cot=req.cot,
        seed=req.seed,
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)
    out: dict[str, Any] = _finish(job_id, _to_dict(result))
    report_progress(100.0)
    return out


def yue_cover_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.yue.cover`` (zero-shot cover)."""
    from common_lib.modules.audio_processing.schemas.yue import YuECoverRequest

    job_id: str = _record_id(record)
    req: Any = YuECoverRequest(**_record_params(record))
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()
    result: Any = _yue_generator().cover(
        audio_path=req.audio_path,
        target_style=req.target_style,
        new_lyrics=req.new_lyrics,
        retain_harmony=req.retain_harmony,
        seed=req.seed,
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)
    out: dict[str, Any] = _finish(job_id, _to_dict(result))
    report_progress(100.0)
    return out


def yue_edit_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.yue.edit`` (conversational score editing)."""
    from common_lib.modules.audio_processing.agents.music_editor import edit_music
    from common_lib.modules.audio_processing.schemas.yue import YuEEditRequest

    job_id: str = _record_id(record)
    req: Any = YuEEditRequest(**_record_params(record))
    if not req.abc:
        raise ValueError("Missing 'abc' score in job params")
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()
    result: Any = edit_music(
        abc=req.abc,
        instruction=req.instructions,
        target_style=req.target_style,
        new_lyrics=req.new_lyrics,
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)
    out: dict[str, Any] = _finish(job_id, _to_dict(result))
    report_progress(100.0)
    return out


# ---------------------------------------------------------------------------
# Longform preview (reuses the route module's chapter helpers)
# ---------------------------------------------------------------------------


async def _longform_preview_async(job_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Render one longform chapter for audition (async body of the job)."""
    from app.modules.audio.routes.longform import (
        LongformPreviewRequest,
        _expressive_opts,
        _prepare_synth,
        _render_chapter_cached,
        _resolve_default_language,
        parse_script_to_spans,
    )
    from common_lib.modules.audio_processing.projects.config import OUTPUTS_DIR
    from common_lib.modules.audio_processing.services.audiobook import (
        AudiobookPlan,
        Chapter,
        Span,
    )

    request: Any = LongformPreviewRequest(**params)
    chapter_index: int = int(request.chapter_index or 0)
    default_voice: Optional[str] = request.default_voice
    language: Optional[str] = request.language
    lexicon: Any = request.lexicon
    voice_map: Any = request.voice_map

    plan_chapters: list[dict[str, Any]] = parse_script_to_spans(
        request.text, default_voice=default_voice
    )
    if not plan_chapters:
        raise ValueError("no chapters parsed from the script")
    total: int = len(plan_chapters)
    if not 0 <= chapter_index < total:
        raise ValueError(f"chapter_index out of range (0..{total - 1})")

    plan = AudiobookPlan(
        chapters=[
            Chapter(title=c["title"], spans=[Span(**s) for s in c["spans"]])
            for c in plan_chapters
        ]
    )
    chapter = plan.chapters[chapter_index]
    cache_dir: str = os.path.join(OUTPUTS_DIR, "longform_cache")
    os.makedirs(cache_dir, exist_ok=True)
    resolved_lang: Any = _resolve_default_language(language, default_voice)

    opts: Any = _expressive_opts(request)
    synth, sr, resolve, engine_id = await _prepare_synth(
        default_voice, resolved_lang, opts, voice_map
    )
    wav_path, duration, was_cached, _ = await _render_chapter_cached(
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
    return {
        "output": os.path.relpath(wav_path, OUTPUTS_DIR),
        "duration_s": round(float(duration), 2),
        "cached": bool(was_cached),
        "title": chapter.title,
        "chapter_index": chapter_index,
        "chapters": total,
    }


def longform_preview_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.longform.preview`` (single chapter TTS)."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()
    payload: dict[str, Any] = _run_async(
        lambda: _longform_preview_async(job_id, params)
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)
    out: dict[str, Any] = _finish(job_id, payload)
    report_progress(100.0)
    return out


# ---------------------------------------------------------------------------
# Export / import / effects (sync engines)
# ---------------------------------------------------------------------------


def export_batch_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.export.batch`` (N-file encode loop)."""
    from pathlib import Path

    from common_lib.modules.audio_processing.editing.exporter import (
        AudioExporter,
        AudioFormat,
        BitDepth,
        ExportConfig,
    )
    from common_lib.modules.audio_processing.schemas import BatchExportRequest

    job_id: str = _record_id(record)
    request: Any = BatchExportRequest(**_record_params(record))
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    config = ExportConfig(
        format=AudioFormat(request.output_format),
        bit_depth=BitDepth(request.bit_depth),
        sample_rate=request.sample_rate,
        normalize=request.normalize,
    )
    if request.platform_preset:
        config.apply_preset(request.platform_preset)

    report_progress(15.0)
    results: Any = AudioExporter().batch_export(
        request.input_paths, request.output_dir, config
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    resp_results: list[dict[str, Any]] = [
        {
            "audio_url": r.output_path,
            "filename": Path(r.output_path).name,
            "format": r.format,
            "sample_rate": r.sample_rate,
            "bit_depth": r.bit_depth,
            "channels": r.channels,
            "duration_seconds": r.duration_seconds,
            "peak_dbfs": r.peak_dbfs,
            "lufs_integrated": r.lufs_integrated,
            "true_peak_dbtp": r.true_peak_dbtp,
            "file_size_bytes": r.file_size_bytes,
            "metadata": r.metadata,
        }
        for r in results
    ]
    payload: dict[str, Any] = {
        "results": resp_results,
        "total": len(request.input_paths),
        "success": len(results),
        "failed": len(request.input_paths) - len(results),
    }
    out: dict[str, Any] = _finish(job_id, payload)
    report_progress(100.0)
    return out


def import_batch_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.import.batch`` (N-file decode/analyze)."""
    from common_lib.modules.audio_processing.editing.importer import AudioImporter
    from common_lib.modules.audio_processing.schemas import BatchImportRequest

    job_id: str = _record_id(record)
    request: Any = BatchImportRequest(**_record_params(record))
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    report_progress(15.0)
    successes, failures = AudioImporter().batch_import(
        request.source_paths, copy=request.copy_to_library
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    resp_successes: list[dict[str, Any]] = [
        {
            "path": r.path,
            "filename": r.filename,
            "format": r.format,
            "sample_rate": r.sample_rate,
            "channels": r.channels,
            "duration_seconds": r.duration_seconds,
            "bit_depth": r.bit_depth,
            "peak_dbfs": r.peak_dbfs,
            "detected_bpm": r.detected_bpm,
            "metadata": r.metadata,
        }
        for r in successes
    ]
    payload: dict[str, Any] = {
        "successes": resp_successes,
        "failures": failures,
        "total": len(request.source_paths),
    }
    out: dict[str, Any] = _finish(job_id, payload)
    report_progress(100.0)
    return out


def effects_chain_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.effects.chain`` (per-effect DSP loop)."""
    import soundfile as sf

    from common_lib.modules.audio_processing.editing.effects import (
        DistortionEffects,
        DynamicsProcessor,
        EQProcessor,
        PitchEffects,
        TimeBasedEffects,
    )
    from common_lib.modules.audio_processing.schemas import EffectsChainRequest

    job_id: str = _record_id(record)
    request: Any = EffectsChainRequest(**_record_params(record))
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    audio, sample_rate = sf.read(request.audio_path, dtype="float32")
    total: int = max(1, len(request.chain))
    for index, effect in enumerate(request.chain):
        if not effect.enabled:
            continue
        if check_cancel():
            return _cancelled_result()
        effect_type, effect_params = effect.type, effect.params
        if effect_type in ("compressor", "limiter", "gate"):
            method_map: dict[str, str] = {
                "compressor": "compress",
                "limiter": "limit",
                "gate": "gate",
            }
            audio = getattr(
                DynamicsProcessor(), method_map.get(effect_type, effect_type)
            )(audio, sample_rate, **effect_params)
        elif effect_type == "eq":
            audio = EQProcessor().process(audio, sample_rate, **effect_params)
        elif effect_type in ("reverb", "delay", "chorus", "flanger", "phaser"):
            audio = TimeBasedEffects().apply(
                audio, sample_rate, effect_type, **effect_params
            )
        elif effect_type in ("distortion", "saturation", "bitcrusher"):
            audio = DistortionEffects().apply(
                audio, sample_rate, effect_type, **effect_params
            )
        elif effect_type in ("pitch_shift", "vocoder"):
            audio = PitchEffects().apply(
                audio, sample_rate, effect_type, **effect_params
            )
        report_progress(10.0 + 70.0 * (index + 1) / total)

    filename: str = f"effects_{job_id}.wav"
    output_path: str = os.path.join(str(_audio_service().output_dir), filename)
    sf.write(output_path, audio, sample_rate)
    report_progress(95.0)
    payload: dict[str, Any] = {
        "audio_url": f"/generated/audio/{filename}",
        "filename": filename,
        "duration_seconds": len(audio) / sample_rate,
        "effects_applied": [e.type for e in request.chain if e.enabled],
        "metadata": {"sample_rate": sample_rate},
    }
    out: dict[str, Any] = _finish(job_id, payload, extra_files=(filename,))
    report_progress(100.0)
    return out


# ---------------------------------------------------------------------------
# Dubbing (stem separation + yt-dlp ingest)
# ---------------------------------------------------------------------------


def dub_clone_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.dub.clone`` (vocals + per-speaker clones)."""
    from common_lib.modules.audio_processing.dubbing import speaker_clone as sc

    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    audio_path: str = str(params.get("audio_path", ""))
    out_dir: str = str(params.get("out_dir", ""))
    if not audio_path:
        raise ValueError("Missing required 'audio_path' param")
    if not out_dir:
        raise ValueError("Missing required 'out_dir' param")
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    report_progress(15.0)
    vocals: Optional[str] = sc.ensure_vocals_track(
        audio_path, out_dir, vocals_path=params.get("vocals_path") or None
    )
    if check_cancel():
        return _cancelled_result()
    if params.get("vocals_path") and not vocals:
        vocals = str(params.get("vocals_path"))
    if not vocals:
        return _finish(
            job_id, {"status": "ok", "found": False, "clones": {}, "refs": {}}
        )

    report_progress(50.0)
    clones: Any = sc.extract_speaker_clones(
        vocals,
        params.get("segments"),
        out_dir,
        labels_source=params.get("labels_source"),
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(80.0)
    refs: Any = sc.extract_segment_refs(vocals, params.get("segments"), out_dir)
    payload: dict[str, Any] = {
        "status": "ok",
        "found": True,
        "vocals_path": vocals,
        "clones": clones,
        "refs": refs,
    }
    out: dict[str, Any] = _finish(job_id, payload)
    report_progress(100.0)
    return out


def dub_ingest_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``audio.dub.ingest_url`` (yt-dlp media + subs)."""
    import hashlib
    import tempfile

    from common_lib.modules.audio_processing.dubbing import ingest as dub_ingest

    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    url: str = str(params.get("url", ""))
    if not url:
        raise ValueError("Missing required 'url' param")
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    out_dir: str = str(params.get("out_dir") or "")
    if not out_dir:
        digest: str = hashlib.sha256(url.encode()).hexdigest()[:12]
        out_dir = os.path.join(tempfile.gettempdir(), f"dub_ingest_{digest}")
        os.makedirs(out_dir, exist_ok=True)

    report_progress(15.0)
    result: dict[str, Any] = dict(
        dub_ingest.ingest_url(
            url,
            out_dir,
            fetch_subs=params.get("fetch_subs", True),
            sub_langs=params.get("sub_langs"),
        )
    )
    if check_cancel():
        return _cancelled_result()
    status: str = str(result.get("status", "ok"))
    if status == "error":
        raise RuntimeError(str(result.get("reason", "ingest failed")))
    report_progress(90.0)
    out: dict[str, Any] = _finish(job_id, result, status=status)
    report_progress(100.0)
    return out


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_EXECUTORS: tuple[tuple[str, Callable[..., Any], str, float], ...] = (
    # Core speech / music
    (TTS_KIND, tts_executor, GPU, 900.0),
    (SPEAK_KIND, speak_executor, GPU, 1800.0),
    (TRANSCRIBE_KIND, transcribe_executor, GPU, 1800.0),
    (VOICE_CLONE_KIND, voice_clone_executor, GPU, 1800.0),
    (SINGING_KIND, singing_executor, GPU, TIMEOUT_GPU),
    (MUSIC_KIND, music_executor, GPU, TIMEOUT_GPU),
    (SFX_KIND, sfx_executor, GPU, 900.0),
    (ADVANCED_TTS_KIND, advanced_tts_executor, GPU, 1200.0),
    # Processing / editing
    (EDIT_KIND, edit_executor, GPU, TIMEOUT_GPU),
    (STEMS_KIND, stems_executor, GPU, TIMEOUT_GPU_LONG),
    (ANALYZE_KIND, analyze_executor, CPU, TIMEOUT_CPU),
    (MASTERING_KIND, mastering_executor, CPU, TIMEOUT_CPU),
    (RESTORATION_KIND, restoration_executor, GPU, TIMEOUT_GPU),
    (TIME_PITCH_KIND, time_pitch_executor, CPU, TIMEOUT_CPU),
    (ARRANGEMENT_KIND, arrangement_executor, CPU, TIMEOUT_CPU),
    # Speech-to-speech
    (STS_CONVERT_KIND, sts_convert_executor, GPU, TIMEOUT_GPU),
    (STS_ACCENT_KIND, sts_accent_executor, GPU, TIMEOUT_GPU),
    (STS_EMOTION_KIND, sts_emotion_executor, GPU, TIMEOUT_GPU),
    # Long form / full song / orchestra
    (FULL_SONG_KIND, full_song_executor, GPU, TIMEOUT_GPU_LONG),
    (ORCHESTRA_KIND, orchestra_executor, GPU, TIMEOUT_GPU_LONG),
    (LONGFORM_PREVIEW_KIND, longform_preview_executor, GPU, TIMEOUT_GPU),
    # YuE
    (YUE_GENERATE_KIND, yue_generate_executor, GPU, TIMEOUT_GPU_LONG),
    (YUE_PLAN_KIND, yue_plan_executor, GPU, TIMEOUT_GPU),
    (YUE_COVER_KIND, yue_cover_executor, GPU, TIMEOUT_GPU_LONG),
    (YUE_EDIT_KIND, yue_edit_executor, CPU, TIMEOUT_CPU),
    # IO / DSP
    (EXPORT_BATCH_KIND, export_batch_executor, CPU, TIMEOUT_GPU),
    (IMPORT_BATCH_KIND, import_batch_executor, CPU, TIMEOUT_CPU),
    (EFFECTS_CHAIN_KIND, effects_chain_executor, CPU, TIMEOUT_CPU),
    # Dubbing
    (DUB_CLONE_KIND, dub_clone_executor, GPU, TIMEOUT_GPU),
    (DUB_INGEST_KIND, dub_ingest_executor, CPU, TIMEOUT_GPU),
)

_REGISTERED = False


def ensure_audio_executors_registered() -> bool:
    """Register all audio executors with the jobs service (idempotent)."""
    global _REGISTERED
    if _REGISTERED:
        return True
    try:
        from common_lib.modules.jobs.service import get_job_service

        service = get_job_service()
        for kind, fn, device, timeout in _EXECUTORS:
            service.register_executor(kind, fn, device=device, timeout=timeout)
        _REGISTERED = True
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_audio_executors_registered failed: %s", exc)
        return False


__all__ = [
    "ADVANCED_TTS_KIND",
    "ANALYZE_KIND",
    "AUDIO_KIND_PREFIX",
    "ARRANGEMENT_KIND",
    "DUB_CLONE_KIND",
    "DUB_INGEST_KIND",
    "EFFECTS_CHAIN_KIND",
    "EDIT_KIND",
    "EXPORT_BATCH_KIND",
    "FULL_SONG_KIND",
    "IMPORT_BATCH_KIND",
    "LONGFORM_PREVIEW_KIND",
    "MASTERING_KIND",
    "MUSIC_KIND",
    "ORCHESTRA_KIND",
    "RESTORATION_KIND",
    "SFX_KIND",
    "SINGING_KIND",
    "SPEAK_KIND",
    "STEMS_KIND",
    "STS_ACCENT_KIND",
    "STS_CONVERT_KIND",
    "STS_EMOTION_KIND",
    "TIME_PITCH_KIND",
    "TRANSCRIBE_KIND",
    "TTS_KIND",
    "VOICE_CLONE_KIND",
    "YUE_COVER_KIND",
    "YUE_EDIT_KIND",
    "YUE_GENERATE_KIND",
    "YUE_PLAN_KIND",
    "analyze_executor",
    "advanced_tts_executor",
    "arrangement_executor",
    "dub_clone_executor",
    "dub_ingest_executor",
    "edit_executor",
    "effects_chain_executor",
    "ensure_audio_executors_registered",
    "export_batch_executor",
    "full_song_executor",
    "import_batch_executor",
    "longform_preview_executor",
    "mastering_executor",
    "music_executor",
    "orchestra_executor",
    "restoration_executor",
    "sfx_executor",
    "singing_executor",
    "speak_executor",
    "stems_executor",
    "sts_accent_executor",
    "sts_convert_executor",
    "sts_emotion_executor",
    "time_pitch_executor",
    "transcribe_executor",
    "tts_executor",
    "voice_clone_executor",
    "yue_cover_executor",
    "yue_edit_executor",
    "yue_generate_executor",
    "yue_plan_executor",
]
