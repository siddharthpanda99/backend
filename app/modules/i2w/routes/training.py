"""``app.modules.i2w.routes.training`` — training-data CRUD.

Per docs/08_api_contract.md §1.5:

* ``GET  /api/v1/i2w/training/records``
* ``GET  /api/v1/i2w/training/records/{id}``
* ``POST /api/v1/i2w/training/records/{id}/feedback``
* ``POST /api/v1/i2w/training/records/{id}/export``
* ``GET  /api/v1/i2w/training/datasets``
* ``POST /api/v1/i2w/training/eval``
* ``GET  /api/v1/i2w/training/eval/{eval_id}``
* ``GET  /api/v1/i2w/training/golden``
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request, status

from app.modules.i2w.routes._helpers import invoke_i2w
from app.modules.i2w.routes.dependencies import (
    I2W_SCOPE_READ,
    I2W_SCOPE_TRAINING_ADMIN,
    I2W_SCOPE_WRITE,
    _audit_request,
    i2w_deps,
    i2w_identity,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/training/records",
    summary="List training records (admin only).",
    dependencies=i2w_deps(scope=I2W_SCOPE_TRAINING_ADMIN, stage="training"),
    response_model=None,
)
async def list_training_records(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.training.records.list")
    try:
        return invoke_i2w("i2w_training_list_records", limit=limit, offset=offset)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/training/records/{record_id}",
    summary="Get a single training record (admin only).",
    dependencies=i2w_deps(scope=I2W_SCOPE_TRAINING_ADMIN, stage="training"),
    response_model=None,
)
async def get_training_record(record_id: str, request: Request) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.training.records.get")
    # The single-record getter is part of the docs' planned set;
    # surface 501 + a clear pointer to the list endpoint.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Single-record getter is pending the dedicated "
            "i2w_training_get_record wrapper. Use "
            "/api/v1/i2w/training/records (list) in the meantime."
        ),
    )


@router.post(
    "/training/records/{record_id}/feedback",
    summary="Record user feedback on a plan / execution.",
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="training"),
    response_model=None,
)
async def record_feedback(
    record_id: str,
    request: Request,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.training.feedback")
    try:
        return invoke_i2w(
            "i2w_training_submit_feedback",
            record_id=record_id,
            **body,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/training/records/{record_id}/export",
    summary="Trigger JSONL export + upload (admin only).",
    dependencies=i2w_deps(scope=I2W_SCOPE_TRAINING_ADMIN, stage="training"),
    response_model=None,
)
async def export_training_record(
    record_id: str,
    request: Request,
    body: Optional[Dict[str, Any]] = Body(default=None),
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.training.export")
    try:
        return invoke_i2w(
            "i2w_training_export",
            record_ids=[record_id],
            **(body or {}),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/training/datasets",
    summary="List dataset versions (admin only).",
    dependencies=i2w_deps(scope=I2W_SCOPE_TRAINING_ADMIN, stage="training"),
    response_model=None,
)
async def list_datasets(request: Request) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.training.datasets.list")
    # The list-datasets wrapper is part of the docs' planned set
    # (it maps to the Phase 5 ``list_datasets`` method). Until the
    # dedicated @node wrapper lands we surface 501.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Datasets list is pending the i2w_list_datasets wrapper. "
            "See docs/08_api_contract.md §4 wrapper inventory."
        ),
    )


@router.post(
    "/training/eval",
    summary="Run the eval suite against a checkpoint (admin only).",
    dependencies=i2w_deps(scope=I2W_SCOPE_TRAINING_ADMIN, stage="training"),
    response_model=None,
)
async def run_training_eval(
    request: Request,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.training.eval")
    try:
        return invoke_i2w("i2w_training_evaluate", **body)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/training/eval/{eval_id}",
    summary="Get an eval result (admin only).",
    dependencies=i2w_deps(scope=I2W_SCOPE_TRAINING_ADMIN, stage="training"),
    response_model=None,
)
async def get_eval_result(eval_id: str, request: Request) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.training.eval.get")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Eval-result getter is pending the dedicated wrapper. "
            "The current eval suite returns the result inline via "
            "i2w_training_evaluate."
        ),
    )


@router.get(
    "/training/golden",
    summary="List golden records (admin only).",
    dependencies=i2w_deps(scope=I2W_SCOPE_TRAINING_ADMIN, stage="training"),
    response_model=None,
)
async def list_golden_records(request: Request) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.training.golden.list")
    # Golden records live on disk in tests/regression/scenarios/
    # (per docs/10 §6). Phase 5 stores them in the DB but the
    # @node wrapper is not yet registered.
    return {
        "status": "ok",
        "note": (
            "Golden records are loaded from "
            "common_lib.modules.orchestration.instruction_to_workflow"
            ".tests.regression.scenarios (Phase 5 in-memory store)."
        ),
        "golden_records": [],
    }


__all__ = ["router"]
