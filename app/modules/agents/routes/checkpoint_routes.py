"""Context checkpoint routes — manage surgical/destructive conversation checkpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.modules.common.types.index import APIResponse
from common_lib.modules.agents.services.checkpoint_service import CheckpointService
from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)

router = APIRouter()


class CheckpointRead(BaseModel):
    id: str
    session_id: str
    checkpoint_index: int
    message_range_start: str | None
    message_range_end: str | None
    summary: str
    token_estimate: int
    tier: str
    created_at: str | None


class ThresholdCheckRequest(BaseModel):
    context_window_size: int
    current_token_count: int


class ContextAssemblyResponse(BaseModel):
    context: list[dict[str, str]]
    checkpoint_count: int


@router.get("/{session_id}", response_model=APIResponse[List[CheckpointRead]])
def list_checkpoints(
    session_id: str,
    db: Session = Depends(get_db_session),
):
    svc = CheckpointService()
    checkpoints = svc.get_checkpoints(db, session_id)
    return APIResponse(
        data=[
            CheckpointRead(
                id=c.id,
                session_id=c.session_id,
                checkpoint_index=c.checkpoint_index,
                message_range_start=c.message_range_start,
                message_range_end=c.message_range_end,
                summary=c.summary,
                token_estimate=c.token_estimate,
                tier=c.tier,
                created_at=c.created_at.isoformat() if c.created_at else None,
            )
            for c in checkpoints
        ],
        message="Retrieved checkpoints",
    )


@router.get("/{session_id}/latest", response_model=APIResponse[CheckpointRead | None])
def get_latest_checkpoint(
    session_id: str,
    db: Session = Depends(get_db_session),
):
    svc = CheckpointService()
    cp = svc.get_latest_checkpoint(db, session_id)
    if not cp:
        return APIResponse(data=None, message="No checkpoints found")
    return APIResponse(
        data=CheckpointRead(
            id=cp.id,
            session_id=cp.session_id,
            checkpoint_index=cp.checkpoint_index,
            message_range_start=cp.message_range_start,
            message_range_end=cp.message_range_end,
            summary=cp.summary,
            token_estimate=cp.token_estimate,
            tier=cp.tier,
            created_at=cp.created_at.isoformat() if cp.created_at else None,
        ),
        message="Retrieved latest checkpoint",
    )


@router.post("/{session_id}/check-threshold")
def check_threshold(
    session_id: str,
    req: ThresholdCheckRequest,
    db: Session = Depends(get_db_session),
):
    svc = CheckpointService()
    tier = svc.check_threshold(
        db, session_id, req.context_window_size, req.current_token_count
    )
    return APIResponse(
        data={"session_id": session_id, "threshold_exceeded": tier},
        message="Threshold check complete",
    )
