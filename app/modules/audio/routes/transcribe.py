"""Transcription Studio thin routes — transport ONLY.

Delegates every operation to
``common_lib.modules.audio_processing.services.asr_service``. No business
logic lives here beyond calling the service and persisting the run
manifest side-effects the spec demands.

Endpoints (mounted under /api/v1/audio, paths appended verbatim):
  POST /transcribe/upload    — upload audio, transcribe, write manifest
  GET  /transcribe/{run_id}  — one run manifest (404 when missing)
  GET  /transcribe           — list manifests, newest first (best-effort)

Why the upload is NOT at ``POST /transcribe``: that exact path is owned by
the legacy jobs-backed transcribe handler in ``router.py`` (registered in
the main audio router before this merge, backed by contract tests and the
voice-dictation hook). FastAPI matches the first registered route, so
registering a multipart handler at ``POST /transcribe`` would leave it
inert (legacy wins, uploads -> 422), or, if it were forced first, would
break every JSON caller of the legacy endpoint. ``POST /transcribe/upload``
keeps both contracts alive. See the track-A report for the collision and
the one-line reorder if the legacy path is later retired.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from common_lib.paths import RESOURCES_ROOT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcribe", tags=["Transcription Studio"])

_TRANSCRIBE_ROOT = RESOURCES_ROOT / "generated_content" / "transcribe"

# Transport-level upload sanity: accepted audio extensions. Anything else is
# stored as .bin — the ASR engines probe content, not the extension.
_ALLOWED_EXTS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
    ".aac",
    ".opus",
    ".wma",
    ".webm",
    ".mp4",
    ".mkv",
    ".aiff",
    ".aif",
}

_RUN_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")
_MANIFEST_SUFFIX = ".manifest.json"


def _run_dir(run_id: str) -> Path:
    return _TRANSCRIBE_ROOT / run_id


def _manifest_path(run_id: str) -> Path:
    return _run_dir(run_id) / f"{run_id}{_MANIFEST_SUFFIX}"


def _check_run_id(run_id: str) -> str:
    if not run_id or not _RUN_ID_RE.fullmatch(run_id):
        raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")
    return run_id


def _entry_ext(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix in _ALLOWED_EXTS else ".bin"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sort_key(doc: dict, fallback_path: Path) -> float:
    created = doc.get("created_at")
    if isinstance(created, str):
        try:
            return datetime.fromisoformat(created).timestamp()
        except ValueError:
            pass
    try:
        return fallback_path.stat().st_mtime
    except OSError:
        return 0.0


@router.post("/upload")
async def transcribe_upload(
    file: UploadFile = File(...),
    language: str | None = Form(None),
    engine_id: str = Form("auto"),
) -> dict:
    from common_lib.modules.audio_processing.services.asr_service import (
        TranscribeServiceError,
        transcribe_file,
    )

    run_id = uuid.uuid4().hex
    run_dir = _run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    ext = _entry_ext(file.filename)
    input_name = f"input{ext}"
    input_path = run_dir / input_name

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="uploaded file is empty")
    try:
        input_path.write_bytes(content)
    except OSError as exc:
        logger.exception("failed to persist upload for run %s", run_id)
        raise HTTPException(
            status_code=500, detail=f"could not store upload: {exc}"
        ) from exc

    try:
        result = transcribe_file(
            str(input_path),
            lang_hint=language,
            engine_id=engine_id or "auto",
        )
    except TranscribeServiceError as exc:
        logger.warning("transcription run %s failed: %s", run_id, exc)
        raise HTTPException(
            status_code=502,
            detail={
                "message": exc.message,
                "reason": exc.reason,
                "engine_id": exc.engine_id,
                "run_id": run_id,
            },
        ) from exc

    manifest = {
        "run_id": run_id,
        "input_filename": input_name,
        "ok": result.get("ok", True),
        "model": result.get("model"),
        "language": result.get("language"),
        "text": result.get("text", ""),
        "segments": result.get("segments", []),
        "duration_s": result.get("duration_s"),
        "created_at": _iso_now(),
    }
    try:
        _manifest_path(run_id).write_text(json.dumps(manifest, indent=2))
    except OSError as exc:
        logger.exception("failed to write manifest for run %s", run_id)
        raise HTTPException(
            status_code=500, detail=f"could not write manifest: {exc}"
        ) from exc

    return manifest


@router.get("/{run_id}")
def get_manifest(run_id: str) -> dict:
    _check_run_id(run_id)
    path = _manifest_path(run_id)
    if not path.is_file():
        # Fallback: any manifest under the run dir (mirrors voice_studio).
        run_dir = _run_dir(run_id)
        hits = list(run_dir.rglob(f"*{_MANIFEST_SUFFIX}")) if run_dir.is_dir() else []
        path = hits[0] if hits else path
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")
    try:
        with path.open() as fh:
            return json.load(fh)
    except Exception as exc:  # noqa: BLE001 — a corrupted manifest is a 500, not a crash
        logger.exception("manifest unreadable: %s", path)
        raise HTTPException(
            status_code=500, detail=f"manifest unreadable: {exc}"
        ) from exc


@router.get("")
def list_manifests() -> dict:
    runs: list[dict] = []
    if _TRANSCRIBE_ROOT.is_dir():
        for manifest_path in _TRANSCRIBE_ROOT.rglob(f"*{_MANIFEST_SUFFIX}"):
            try:
                with manifest_path.open() as fh:
                    doc = json.load(fh)
                if not isinstance(doc, dict):
                    continue
                doc.setdefault("run_id", manifest_path.parent.name)
                doc["_mtime"] = _sort_key(doc, manifest_path)
                runs.append(doc)
            except Exception:  # noqa: BLE001 — corrupt entries are skipped, never fatal
                logger.debug("skipping invalid manifest %s", manifest_path)
                continue
    runs.sort(key=lambda d: d.get("_mtime", 0.0), reverse=True)
    for doc in runs:
        doc.pop("_mtime", None)
    return {"runs": runs, "count": len(runs), "schema_version": 1}
