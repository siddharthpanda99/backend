"""Doc Processing module API routes — PDF extraction, text/metadata/tables.

Thin routing layer that delegates to common_lib.modules.doc_processing services.
Heavy ops run jobs-backed; pass ``sync=true`` to run inline and get the legacy synchronous response.
"""

from __future__ import annotations

import json
import logging
import asyncio
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.doc_processing.runtime.actor import capture_job_actor, owned_job_service
from common_lib.modules.jobs.artifacts import job_dir
from common_lib.modules.jobs.models import JobRecord
from common_lib.modules.jobs.service import get_job_service

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(capture_job_actor)])


class ExtractRequest(BaseModel):
    file_path: str
    options: Optional[Dict[str, Any]] = None


class ExtractTextRequest(BaseModel):
    file_path: str
    pages: Optional[str] = None


class ExtractTablesRequest(BaseModel):
    file_path: str
    pages: Optional[str] = None


class ExtractMetadataRequest(BaseModel):
    file_path: str


# ---------------------------------------------------------------------------
# Jobs-backed execution helpers
# ---------------------------------------------------------------------------


def _ensure_doc_processing_jobs():
    """Register doc_processing executors and return the actor-aware JobService proxy."""
    return owned_job_service()


def _doc_processing_job_payload(record: Any) -> Dict[str, Any]:
    refs: List[str] = []
    try:
        refs = [str(r) for r in (record.get_result_refs() or [])]
    except Exception:
        refs = []
    return {
        "job_id": str(record.id),
        "status": str(record.status),
        "kind": str(record.kind),
        "progress": float(record.progress or 0.0),
        "result_refs": refs,
        "error": record.error,
    }


def _doc_processing_job_status(job_id: str) -> Dict[str, Any]:
    """Jobs-backed status view."""
    from fastapi import HTTPException as _HTTPException

    svc = _ensure_doc_processing_jobs()
    record = svc.get(job_id)
    if record is None:
        raise _HTTPException(status_code=404, detail=f"Job {job_id} not found")
    payload: Dict[str, Any] = _doc_processing_job_payload(record)
    meta: Dict[str, Any] = {}
    try:
        refs = [str(r) for r in (record.get_result_refs() or [])]
    except Exception:
        refs = []
    for ref in refs:
        if not ref.endswith("result.json"):
            continue
        try:
            with open(ref, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                meta = loaded
                break
        except (OSError, ValueError):
            continue
    payload["meta"] = meta
    return payload


# ---------------------------------------------------------------------------
# Jobs endpoints
# ---------------------------------------------------------------------------


@router.get("/jobs")
async def list_doc_processing_jobs(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List background doc_processing jobs (newest first), newest-first with filters."""
    records = _ensure_doc_processing_jobs().list(
        status=status,
        kind=kind,
        kind_prefix="doc_processing.",
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
    )
    items = [_doc_processing_job_payload(record) for record in records]
    return {"data": items, "total": len(items)}


@router.get("/jobs/{job_id}")
async def get_doc_processing_job(job_id: str) -> Dict[str, Any]:
    """Poll a jobs-backed doc_processing job (progress, result_refs, result.json meta)."""
    return _doc_processing_job_status(job_id)


@router.post("/jobs/{job_id}/cancel")
async def cancel_doc_processing_job(job_id: str) -> Dict[str, Any]:
    """Cooperatively cancel a queued/running doc_processing job."""
    record = _ensure_doc_processing_jobs().cancel(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"status": "ok", **_doc_processing_job_payload(record)}


@router.get("/jobs/{job_id}/events")
async def doc_processing_job_events(job_id: str):
    """Stream SSE progress events backed by doc_processing job progress."""
    from fastapi.responses import StreamingResponse

    async def event_generator():
        import time as _time

        deadline: float = _time.time() + 3600.0
        last_progress: float = -1.0
        yield f"event: started\ndata: {json.dumps({'job_id': job_id, 'status': 'queued'})}\n\n"
        while True:
            record: JobRecord | None = get_job_service().get(job_id)
            if record is None:
                yield f"event: failed\ndata: {json.dumps({'job_id': job_id, 'error': 'job not found'})}\n\n"
                return
            if record.progress != last_progress:
                last_progress = record.progress
                yield f"event: progress\ndata: {json.dumps({'job_id': job_id, 'status': record.status, 'progress': record.progress})}\n\n"
            if record.status in ("completed", "failed", "cancelled"):
                if record.status == "completed":
                    meta: Dict[str, Any] = {}
                    for ref in _doc_processing_job_payload(record)["result_refs"]:
                        if not ref.endswith("result.json"):
                            continue
                        try:
                            with open(ref, "r", encoding="utf-8") as fh:
                                loaded = json.load(fh)
                            if isinstance(loaded, dict):
                                meta = loaded
                                break
                        except (OSError, ValueError):
                            continue
                    yield f"event: completed\ndata: {json.dumps({'job_id': job_id, 'status': 'completed', 'meta': meta})}\n\n"
                else:
                    yield f"event: {record.status}\ndata: {json.dumps({'job_id': job_id, 'status': record.status, 'error': record.error or record.status})}\n\n"
                return
            if _time.time() > deadline:
                yield f"event: timeout\ndata: {json.dumps({'job_id': job_id, 'error': 'progress stream timed out'})}\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/extract")
async def extract_full(request: ExtractRequest, sync: bool = False) -> Dict[str, Any]:
    """Full PDF extraction (text + metadata + tables). Jobs-backed by default."""
    if sync:
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import PDFExtractionPipeline
            svc = PDFExtractionPipeline()
            result = svc.extract(request.file_path, **(request.options or {})) if hasattr(svc, "extract") else {"file": request.file_path}
            return {"result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    from app.modules.doc_processing.runtime.job_executors import EXTRACT_FULL_KIND

    record = _ensure_doc_processing_jobs().submit(
        EXTRACT_FULL_KIND,
        params={"file_path": request.file_path, "options": request.options or {}},
    )
    return {"status": "queued", **_doc_processing_job_payload(record)}


@router.post("/extract/text")
async def extract_text(request: ExtractTextRequest, sync: bool = False) -> Dict[str, Any]:
    """Extract text from PDF. Jobs-backed by default."""
    if sync:
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import PDFExtractionPipeline
            svc = PDFExtractionPipeline()
            result = svc.extract_text(request.file_path, pages=request.pages) if hasattr(svc, "extract_text") else {"text": ""}
            return {"result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    from app.modules.doc_processing.runtime.job_executors import EXTRACT_TEXT_KIND

    record = _ensure_doc_processing_jobs().submit(
        EXTRACT_TEXT_KIND,
        params={"file_path": request.file_path, "pages": request.pages},
    )
    return {"status": "queued", **_doc_processing_job_payload(record)}


@router.post("/extract/tables")
async def extract_tables(request: ExtractTablesRequest, sync: bool = False) -> Dict[str, Any]:
    """Extract tables from PDF. Jobs-backed by default."""
    if sync:
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import PDFExtractionPipeline
            svc = PDFExtractionPipeline()
            result = svc.extract_tables(request.file_path, pages=request.pages) if hasattr(svc, "extract_tables") else {"tables": []}
            return {"result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    from app.modules.doc_processing.runtime.job_executors import EXTRACT_TABLES_KIND

    record = _ensure_doc_processing_jobs().submit(
        EXTRACT_TABLES_KIND,
        params={"file_path": request.file_path, "pages": request.pages},
    )
    return {"status": "queued", **_doc_processing_job_payload(record)}


@router.post("/extract/metadata")
async def extract_metadata(request: ExtractMetadataRequest, sync: bool = False) -> Dict[str, Any]:
    """Extract metadata from PDF. Jobs-backed by default."""
    if sync:
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import PDFExtractionPipeline
            svc = PDFExtractionPipeline()
            result = svc.extract_metadata(request.file_path) if hasattr(svc, "extract_metadata") else {"metadata": {}}
            return {"result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    from app.modules.doc_processing.runtime.job_executors import EXTRACT_METADATA_KIND

    record = _ensure_doc_processing_jobs().submit(
        EXTRACT_METADATA_KIND,
        params={"file_path": request.file_path},
    )
    return {"status": "queued", **_doc_processing_job_payload(record)}


@router.get("/parsers")
async def list_parsers() -> Dict[str, Any]:
    """List available parsers."""
    try:
        from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import PDFExtractionPipeline
        svc = PDFExtractionPipeline()
        result = svc.list_parsers() if hasattr(svc, "list_parsers") else []
        return {"parsers": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))