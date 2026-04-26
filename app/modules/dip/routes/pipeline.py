from fastapi import APIRouter, Body, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from common_lib.modules.dip.pipeline.controller import (
    run_pipeline,
    get_pipeline_executions,
    get_pipeline_status,
    validate_workflow,
)

router = APIRouter(prefix="/dip/pipeline", tags=["dip/pipeline"])
pipeline_router = router


class PipelineRunRequest(BaseModel):
    name: str
    workflow_yaml: str
    source_folder: str
    output_dest: str = "raw"


class ValidateRequest(BaseModel):
    workflow_yaml: str


@router.post("/run")
async def create_pipeline_run(req: PipelineRunRequest):
    return await run_pipeline(
        req.name, req.workflow_yaml, req.source_folder, req.output_dest
    )


@router.get("/executions")
async def list_executions():
    return await get_pipeline_executions()


@router.get("/status/{execution_id}")
async def get_execution_status(execution_id: str):
    return await get_pipeline_status(execution_id)


@router.post("/validate")
async def validate(req: ValidateRequest):
    return await validate_workflow(req.workflow_yaml)
