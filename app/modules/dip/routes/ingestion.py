from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
    BackgroundTasks,
    Query,
)
from fastapi.responses import StreamingResponse
import uuid
import os
from typing import List, Optional, Any
from common_lib.modules.dip.ingestion.controller import (
    process_documents,
    get_processing_status,
    list_parsers,
    parse_file_with_comparator,
    parse_file_with_comparator_content,
    save_extracted_text,
    get_extraction_stats,
    get_ingestion_sources,
)
from common_lib.modules.dip.document_vault import (
    list_documents,
    get_document,
    delete_document,
    rename_document,
)
from common_lib.modules.notification.controller import stream_notifications, Channels

router = APIRouter(prefix="/dip/ingestion", tags=["dip/ingestion"])


@router.post("/process")
async def upload_and_process(
    files: List[UploadFile] = File(...),
    parser: str = Form("pypdf"),
    compare_mode: bool = Form(False),
    output_dest: str = Form("raw"),
):
    return await process_documents(files, parser, compare_mode, output_dest)


@router.post("/compare")
async def compare_parsers(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    parsers: Optional[str] = Form(None),
):
    parser_list = parsers.split(",") if parsers else None
    # Read file content before passing to background task
    content = await file.read()
    filename = file.filename
    job_id = str(uuid.uuid4())

    # Offload to background and notify via SSE
    background_tasks.add_task(
        parse_file_with_comparator_content,
        content,
        filename,
        parser_list,
        job_id=job_id,
    )

    return {"job_id": job_id, "filename": filename, "status": "started"}


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
):
    """Save extracted text to storage and vault."""
    import json

    ext_results = None
    meta = None
    try:
        if extraction_results:
            ext_results = json.loads(extraction_results)
        if metadata:
            meta = json.loads(metadata)
    except:
        pass

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


@router.get("/stats")
async def get_extraction_stats():
    """Get extraction statistics for Overview tab."""
    return await get_extraction_stats()


@router.get("/sources")
async def get_sources():
    """Get ingestion sources."""
    return await get_ingestion_sources()


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

@router.get("/jobs")
async def list_ingestion_jobs():
    """List recent and active ingestion jobs."""
    return {
        "data": [
            {"id": "job_001", "name": "Quarterly Reports", "status": "completed", "progress": 100},
            {"id": "job_002", "name": "Technical Docs", "status": "processing", "progress": 45}
        ]
    }

@router.get("/metrics")
async def get_ingestion_metrics():
    """Alias for /stats to match UI expectations."""
    from common_lib.modules.dip.ingestion.controller import get_extraction_stats
    return await get_extraction_stats()
