"""Doom loop detection routes."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.modules.common.types.index import APIResponse
from common_lib.modules.agents.services.doom_loop_service import DoomLoopService
from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)

router = APIRouter()


class DoomLoopEventRead(BaseModel):
    id: str
    session_id: str
    detected_pattern: str | None
    tool_calls_snapshot: str | None
    summary: str | None
    action_taken: str
    created_at: str | None


class DoomLoopDetectRequest(BaseModel):
    session_id: str
    tool_calls: list[dict]


class DoomLoopStatsResponse(BaseModel):
    session_id: str
    total_events: int
    events: list[DoomLoopEventRead]


@router.get("/events", response_model=APIResponse[List[DoomLoopEventRead]])
def list_events(
    session_id: str,
    db: Session = Depends(get_db_session),
):
    svc = DoomLoopService()
    events = svc.get_events(db, session_id)
    return APIResponse(
        data=[
            DoomLoopEventRead(
                id=e.id,
                session_id=e.session_id,
                detected_pattern=e.detected_pattern,
                tool_calls_snapshot=e.tool_calls_snapshot,
                summary=e.summary,
                action_taken=e.action_taken,
                created_at=e.created_at.isoformat() if e.created_at else None,
            )
            for e in events
        ],
        message="Retrieved doom loop events",
    )


@router.get("/stats/{session_id}", response_model=APIResponse[DoomLoopStatsResponse])
def get_stats(
    session_id: str,
    db: Session = Depends(get_db_session),
):
    svc = DoomLoopService()
    events = svc.get_events(db, session_id)
    return APIResponse(
        data=DoomLoopStatsResponse(
            session_id=session_id,
            total_events=len(events),
            events=[
                DoomLoopEventRead(
                    id=e.id,
                    session_id=e.session_id,
                    detected_pattern=e.detected_pattern,
                    tool_calls_snapshot=e.tool_calls_snapshot,
                    summary=e.summary,
                    action_taken=e.action_taken,
                    created_at=e.created_at.isoformat() if e.created_at else None,
                )
                for e in events
            ],
        ),
        message="Retrieved doom loop stats",
    )
