from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional
from common_lib.modules.dip.ingestion.controller import (
    process_documents,
    get_processing_status,
    list_parsers,
    parse_file_with_comparator,
)

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
async def compare_parsers(file: UploadFile = File(...)):
    return await parse_file_with_comparator(file)


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    return await get_processing_status(job_id)


@router.get("/parsers")
async def get_parsers():
    return await list_parsers()


from fastapi import APIRouter, Body, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from common_lib.modules.dip.pipeline.controller import (
    run_pipeline,
    get_pipeline_executions,
    get_pipeline_status,
    validate_workflow,
)

pipeline_router = APIRouter(prefix="/dip/pipeline", tags=["dip/pipeline"])


class PipelineRunRequest(BaseModel):
    name: str
    workflow_yaml: str
    source_folder: str
    output_dest: str = "raw"


class ValidateRequest(BaseModel):
    workflow_yaml: str


@pipeline_router.post("/run")
async def create_pipeline_run(req: PipelineRunRequest):
    return await run_pipeline(
        req.name, req.workflow_yaml, req.source_folder, req.output_dest
    )


@pipeline_router.get("/executions")
async def list_executions():
    return await get_pipeline_executions()


@pipeline_router.get("/status/{execution_id}")
async def get_execution_status(execution_id: str):
    return await get_pipeline_status(execution_id)


@pipeline_router.post("/validate")
async def validate(req: ValidateRequest):
    return await validate_workflow(req.workflow_yaml)
