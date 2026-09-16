"""``app.modules.knowledge_engine.compiler.routes.router`` — compiler transport.

Thin router layer (no business logic): validates requests, checks the
Cluster 1 feature-flag gate, and delegates to `common_lib` compiler
services. Auth is enforced at registration (`auth: True`).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/compiler", tags=["Knowledge Compiler"])


class CompileRequest(BaseModel):
    source_id: str = Field(..., min_length=1)
    text: str = Field(default="")
    mime: str = Field(default="text/plain")


class IncrementalRequest(BaseModel):
    doc_id: str = Field(..., min_length=1)
    text: str = Field(default="")
    prior_graph: dict[str, Any] = Field(default_factory=dict)


def _require_flag(flag_name: str) -> None:
    """503 when the master or a sub-flag gate is OFF (explicit)."""
    from common_lib.modules.knowledge_engine.compiler.flags import (
        is_compiler_flag_enabled,
    )

    if not is_compiler_flag_enabled("KNOWLEDGE_COMPILER_ENABLED"):
        raise HTTPException(
            status_code=503,
            detail="Knowledge Compiler disabled (KNOWLEDGE_COMPILER_ENABLED=OFF)",
        )
    if not is_compiler_flag_enabled(flag_name):
        raise HTTPException(
            status_code=503, detail=f"Feature disabled ({flag_name}=OFF)"
        )


@router.post("/compile", response_model=dict[str, Any])
async def compile_source(request: CompileRequest):
    """Dispatch a background compilation job for raw source text."""
    _require_flag("COMPILER_DUAL_REPRESENTATION_ENABLED")
    from common_lib.modules.knowledge_engine.compiler.worker import (
        dispatch_compilation_job,
    )

    return dispatch_compilation_job(request.source_id, request.text, request.mime)


@router.get("/jobs/{job_id}", response_model=dict[str, Any])
async def get_job(job_id: str):
    """Fetch a compilation job record (404 when unknown)."""
    _require_flag("COMPILER_DUAL_REPRESENTATION_ENABLED")
    from common_lib.modules.knowledge_engine.compiler.worker import (
        get_compilation_job,
    )

    job = get_compilation_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"unknown job {job_id}")
    return {"job": job}


@router.post("/compile-incremental", response_model=dict[str, Any])
async def compile_incremental(request: IncrementalRequest):
    """Delta-detect then recompile strictly within the impact set."""
    _require_flag("COMPILER_INCREMENTAL_UPDATES_ENABLED")
    from common_lib.modules.knowledge_engine.compiler.delta_detector import (
        detect_document_deltas,
    )
    from common_lib.modules.knowledge_engine.compiler.incremental_runner import (
        run_incremental_compilation,
    )

    delta = detect_document_deltas(request.doc_id, request.text)
    result = run_incremental_compilation(
        request.doc_id, request.text, delta, request.prior_graph
    )
    return {"delta": delta, **result}
