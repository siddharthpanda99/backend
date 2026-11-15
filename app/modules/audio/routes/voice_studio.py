"""Voice Studio thin routes — transport ONLY.

Delegates every operation to ``common_lib.modules.audio_processing``.

Endpoints (all under /api/v1/audio/studio):
  GET  /engines             — capability registry (unfiltered)
  GET  /voices?engine=<id>  — voice list for one engine (kind=cloned also supported)
  POST /pipeline/validate   — dry-run validation, no side effects
  POST /pipeline/run        — execute a pipeline definition
  GET  /runs                — runs manifest history
  GET  /runs/<run_id>       — full manifest for a run
  GET  /file/<filename>     — audio/wav for a run artifact
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from pydantic import BaseModel

from common_lib.modules.audio_processing.nodes.voice_pipeline import (
    voice_studio_list_engines,
    voice_studio_list_voices,
    voice_studio_validate_pipeline,
    voice_studio_run_pipeline,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/studio", tags=["Voice Studio"])


class PipelineValidateRequest(BaseModel):
    pipeline: dict


class PipelineRunRequest(BaseModel):
    pipeline: dict


def _safe_filename(name: str) -> str:
    if not name or name != Path(name).name or ".." in name or "/" in name:
        raise HTTPException(status_code=404, detail="unknown filename")
    return name


@router.get("/engines")
def engines() -> dict:
    return voice_studio_list_engines()


@router.get("/voices")
def voices(
    engine: str | None = Query(None),
    kind: str | None = Query(None),
) -> dict:
    return voice_studio_list_voices(engine_id=engine)


@router.post("/pipeline/validate")
def validate(req: PipelineValidateRequest) -> dict:
    import json

    return voice_studio_validate_pipeline(json.dumps(req.pipeline))


@router.post("/pipeline/run")
def run(req: PipelineRunRequest) -> dict:
    import json

    return voice_studio_run_pipeline(json.dumps(req.pipeline))


@router.get("/runs")
def runs() -> dict:
    from pathlib import Path as P
    from common_lib.paths import RESOURCES_ROOT

    runs_dir = RESOURCES_ROOT / "generated_content" / "voice-studio" / "runs"
    out = []
    if runs_dir.is_dir():
        for manifest_path in runs_dir.rglob("*.manifest.json"):
            try:
                import json as _json

                with manifest_path.open() as fh:
                    doc = _json.load(fh)
                out.append(
                    {
                        "filename": manifest_path.with_suffix(".wav").name,
                        "engine_id": doc.get("engine"),
                        "engine_label": doc.get("engine"),
                        "duration_s": (doc.get("stats") or {}).get("duration_s"),
                        "rtfi": doc.get("rtf"),
                        "url": f"/api/v1/audio/studio/file/{manifest_path.with_suffix('.wav').name}",
                        "size_bytes": (manifest_path.with_suffix(".wav")).stat().st_size
                        if manifest_path.with_suffix(".wav").is_file()
                        else None,
                        "license": None,
                        "commercial_ok": None,
                        "created_at": doc.get("created_at"),
                    }
                )
            except Exception:
                continue
    return {"runs": out, "schema_version": 1}


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    from common_lib.paths import RESOURCES_ROOT
    import json as _json

    root = RESOURCES_ROOT / "generated_content" / "voice-studio" / "runs" / run_id
    manifest_path = root / f"{run_id}.manifest.json"
    if not manifest_path.is_file():
        # fallback: try any manifest under that run dir
        if root.is_dir():
            hits = list(root.rglob("*.manifest.json"))
            if hits:
                manifest_path = hits[0]
    if not manifest_path.is_file():
        from fastapi import HTTPException as _HTTPException

        raise _HTTPException(status_code=404, detail=f"run {run_id!r} not found")
    with manifest_path.open() as fh:
        doc = _json.load(fh)
    return {"manifest_path": str(manifest_path), "document": doc}


@router.get("/file/{filename}")
def file(filename: str) -> FileResponse:
    from common_lib.paths import RESOURCES_ROOT

    safe = _safe_filename(filename)
    # walk the studio runs dir to locate this filename (support nested run dirs)
    root = RESOURCES_ROOT / "generated_content" / "voice-studio" / "runs"
    path = root / safe
    if not path.is_file():
        hits = list(root.rglob(safe)) if root.is_dir() else []
        if not hits:
            from fastapi import HTTPException as _HTTPException

            raise _HTTPException(status_code=404, detail="file not found")
        path = hits[0]
    return FileResponse(path, media_type="audio/wav", filename=safe)
