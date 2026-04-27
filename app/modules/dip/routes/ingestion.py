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
from typing import List, Optional
from common_lib.modules.dip.ingestion.controller import (
    process_documents,
    get_processing_status,
    list_parsers,
    parse_file_with_comparator,
    parse_file_with_comparator_content,
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
        parse_file_with_comparator_content, content, filename, parser_list, job_id=job_id
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
