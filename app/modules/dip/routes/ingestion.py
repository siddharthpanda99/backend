from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
    BackgroundTasks,
    Query,
    Depends,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uuid
import os
import base64
import json
import asyncio
from typing import Dict, List, Optional, Any
from common_lib.modules.dip.ingestion.controller import (
    process_documents,
    get_processing_status,
    list_parsers,
    list_ingestion_jobs,
    delete_ingestion_job,
    parse_file_with_comparator,
    parse_file_with_comparator_content,
    save_extracted_text,
    get_extraction_stats,
    get_ingestion_sources,
    create_ingestion_source,
    delete_ingestion_source,
    update_ingestion_source,
    sync_ingestion_source,
)
from common_lib.modules.dip.vault_storage import (
    list_documents,
    get_document,
    delete_document,
    rename_document,
)
from common_lib.modules.notification.controller import stream_notifications, Channels

from app.modules.dip.runtime.actor import capture_job_actor, owned_job_service
from common_lib.modules.jobs.artifacts import job_dir
from common_lib.modules.jobs.models import JobRecord
from common_lib.modules.jobs.service import get_job_service

router = APIRouter(prefix="/dip/ingestion", tags=["dip/ingestion"], dependencies=[Depends(capture_job_actor)])


# ---------------------------------------------------------------------------
# Jobs-backed execution helpers
# ---------------------------------------------------------------------------


def _ensure_dip_jobs():
    return owned_job_service()


def _dip_job_payload(record: Any) -> Dict[str, Any]:
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


def _dip_job_status(job_id: str) -> Dict[str, Any]:
    from fastapi import HTTPException as _HTTPException

    svc = _ensure_dip_jobs()
    record = svc.get(job_id)
    if record is None:
        raise _HTTPException(status_code=404, detail=f"Job {job_id} not found")
    payload: Dict[str, Any] = _dip_job_payload(record)
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
async def list_dip_jobs(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    records = _ensure_dip_jobs().list(
        status=status,
        kind=kind,
        kind_prefix="dip.",
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
    )
    items = [_dip_job_payload(record) for record in records]
    return {"data": items, "total": len(items)}


@router.get("/jobs/{job_id}")
async def get_dip_job(job_id: str) -> Dict[str, Any]:
    return _dip_job_status(job_id)


@router.post("/jobs/{job_id}/cancel")
async def cancel_dip_job(job_id: str) -> Dict[str, Any]:
    record = _ensure_dip_jobs().cancel(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"status": "ok", **_dip_job_payload(record)}


@router.get("/jobs/{job_id}/events")
async def dip_job_events(job_id: str):
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
                    for ref in _dip_job_payload(record)["result_refs"]:
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


@router.post("/process")
async def upload_and_process(
    files: List[UploadFile] = File(...),
    parser: str = Form("pypdf"),
    compare_mode: bool = Form(False),
    output_dest: str = Form("raw"),
    sync: bool = False,
):
    """Process documents. Jobs-backed by default; pass ``sync=true`` for inline."""
    if sync:
        return await process_documents(files, parser, compare_mode, output_dest)

    # Convert files to base64 for job params
    file_data = []
    for f in files:
        content = await f.read()
        file_data.append({
            "filename": f.filename,
            "content_type": f.content_type,
            "content": base64.b64encode(content).decode("utf-8"),
        })

    from app.modules.dip.runtime.job_executors import INGESTION_PROCESS_KIND

    record = _ensure_dip_jobs().submit(
        INGESTION_PROCESS_KIND,
        params={"files": file_data, "parser": parser, "compare_mode": compare_mode, "output_dest": output_dest},
    )
    return {"status": "queued", **_dip_job_payload(record)}


@router.post("/compare")
async def compare_parsers(
    file: UploadFile = File(...),
    parsers: Optional[str] = Form(None),
    sync: bool = False,
):
    """Compare parsers. Jobs-backed by default; pass ``sync=true`` for inline (BackgroundTasks)."""
    parser_list = parsers.split(",") if parsers else None
    content = await file.read()
    filename = file.filename
    file_b64 = base64.b64encode(content).decode("utf-8")

    if sync:
        job_id = str(uuid.uuid4())
        from common_lib.modules.dip.ingestion.controller import parse_file_with_comparator_content
        background_tasks = BackgroundTasks()
        background_tasks.add_task(
            parse_file_with_comparator_content,
            content,
            filename,
            parser_list,
            job_id=job_id,
        )
        return {"job_id": job_id, "filename": filename, "status": "started"}

    from app.modules.dip.runtime.job_executors import INGESTION_COMPARE_KIND

    record = _ensure_dip_jobs().submit(
        INGESTION_COMPARE_KIND,
        params={"file_content": file_b64, "filename": filename, "parsers": parsers},
    )
    return {"status": "queued", **_dip_job_payload(record)}


@router.get("/compare/stream")
async def stream_global_compare():
    """Stream all compare jobs via SSE"""

    async def event_generator():
        async for message in stream_notifications(Channels.DIP_COMPARE):
            yield message

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    return await get_processing_status(job_id)


@router.get("/parsers")
async def get_parsers():
    return await list_parsers()


@router.post("/save")
async def save_extraction_results(
    text: str = Form(...),
    parser: str = Form("pypdf"),
    filename: str = Form("document.txt"),
    destination: str = Form("local"),
    extraction_results: Optional[str] = Form(None),  # JSON string of all parser results
    file_content: Optional[bytes] = File(None),  # Raw file for vault
    content_type: str = Form("application/pdf"),
    metadata: Optional[str] = Form(None),  # JSON metadata
    sync: bool = False,
):
    """Save extracted text to storage and vault. Jobs-backed by default; pass ``sync=true`` for inline."""
    import json
    import base64

    ext_results = None
    meta = None
    try:
        if extraction_results:
            ext_results = json.loads(extraction_results)
        if metadata:
            meta = json.loads(metadata)
    except:
        pass

    file_b64 = None
    if file_content:
        file_b64 = base64.b64encode(file_content).decode("utf-8")

    if sync:
        return await save_extracted_text(
            text,
            parser,
            filename,
            destination,
            extraction_results=ext_results,
            file_content=file_content,
            content_type=content_type,
            metadata=meta,
        )

    from app.modules.dip.runtime.job_executors import EXTRACTION_PROCESS_KIND

    record = _ensure_dip_jobs().submit(
        EXTRACTION_PROCESS_KIND,
        params={
            "text": text,
            "parser": parser,
            "filename": filename,
            "destination": destination,
            "extraction_results": ext_results,
            "file_content": file_b64,
            "content_type": content_type,
            "metadata": meta,
        },
    )
    return {"status": "queued", **_dip_job_payload(record)}


@router.get("/stats")
async def get_extraction_stats():
    """Get extraction statistics for Overview tab."""
    return await get_extraction_stats()


@router.get("/sources")
async def get_sources():
    """Get ingestion sources."""
    return await get_ingestion_sources()


class IngestionSourceCreate(BaseModel):
    name: str
    type: str
    config: Optional[dict[str, Any]] = None
    platform: Optional[str] = None
    enabled: bool = True


@router.post("/sources")
async def create_source(payload: IngestionSourceCreate):
    """Create a new ingestion source."""
    result = await create_ingestion_source(
        name=payload.name,
        type=payload.type,
        config=payload.config,
        platform=payload.platform,
        enabled=payload.enabled,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    """Delete an ingestion source."""
    result = await delete_ingestion_source(source_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result


class IngestionSourceUpdate(BaseModel):
    updates: dict[str, Any]


@router.put("/sources/{source_id}")
async def update_source(source_id: str, payload: IngestionSourceUpdate):
    """Update an ingestion source."""
    result = await update_ingestion_source(source_id, payload.updates)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result


@router.post("/sources/{source_id}/sync")
async def sync_source(source_id: str, sync: bool = False):
    """Sync an ingestion source. Jobs-backed by default; pass ``sync=true`` for inline."""
    if sync:
        result = await sync_ingestion_source(source_id)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error"))
        return result

    from app.modules.dip.runtime.job_executors import STORAGE_SYNC_KIND

    record = _ensure_dip_jobs().submit(
        STORAGE_SYNC_KIND,
        params={"source_id": source_id},
    )
    return {"status": "queued", **_dip_job_payload(record)}



@router.get("/vault")
async def get_vault_documents(limit: int = Query(100)):
    """List all documents in vault."""
    return list_documents(limit)


@router.get("/vault/{document_id}")
async def get_vault_document(document_id: str):
    """Get full document with extractions."""
    result = get_document(document_id)
    if not result:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Document not found")
    return result


@router.delete("/vault/{document_id}")
async def delete_vault_document(document_id: str):
    """Delete a document from vault."""
    success = delete_document(document_id)
    if not success:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Document not found")
    return {"success": True}


@router.post("/vault/{document_id}/rename")
async def rename_vault_document(document_id: str, new_filename: str = Form(...)):
    """Rename a document."""
    success = rename_document(document_id, new_filename)
    if not success:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Document not found")
    return {"success": True}

@router.post("/upload")
async def upload_source_file(
    file: UploadFile = File(...),
    parser: str = Form("pypdf"),
    service: Any = None # Placeholder for ingestion service
):
    """Simple upload endpoint for the UI's Ingestion Wizard."""
    # Logic similar to /process but focused on storage
    result = await process_documents([file], parser, False, "vault")
    return {"data": result, "status": "uploaded"}

@router.get("/jobs/stream")
async def stream_job_progress():
    """SSE stream for real-time ingestion job progress updates."""

    async def event_generator():
        async for message in stream_notifications(Channels.INGESTION_PROGRESS):
            yield message

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/jobs")
async def list_jobs():
    """List recent and active ingestion jobs from DB + in-memory tracker."""
    jobs = await list_ingestion_jobs()
    return {"data": jobs}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete an ingestion job record."""
    deleted = delete_ingestion_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"success": True}

@router.get("/metrics")
async def get_ingestion_metrics():
    """Alias for /stats to match UI expectations."""
    from common_lib.modules.dip.ingestion.controller import get_extraction_stats
    return await get_extraction_stats()
