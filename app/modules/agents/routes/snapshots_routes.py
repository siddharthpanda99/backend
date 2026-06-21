"""Snapshot API Routes — thin router delegating to SnapshotService."""

import json
import uuid
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common_lib.modules.agents.models.snapshot_models import AgentSnapshot
from common_lib.modules.agents.services.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Snapshots"])


def get_db():
    from common_lib.modules.data_storage.database.connection import get_session

    for session in get_session():
        yield session


class SnapshotResponse(BaseModel):
    id: str
    session_id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    message_count: int
    is_auto: bool


class CreateSnapshotRequest(BaseModel):
    name: str
    description: Optional[str] = None
    include_memories: bool = True
    include_tool_states: bool = True


class ReplayRequest(BaseModel):
    new_session_name: Optional[str] = None


@router.post("/sessions/{session_id}/snapshots", response_model=SnapshotResponse)
async def create_snapshot(
    session_id: str, request: CreateSnapshotRequest, db=Depends(get_db)
):
    from common_lib.modules.agents.models.session_models import AgentSession

    agent_session = db.get(AgentSession, session_id)
    if not agent_session:
        raise HTTPException(status_code=404, detail="Session not found")

    svc = SnapshotService(db)
    snapshot = svc.create_snapshot(
        session_id=session_id,
        name=request.name,
        agent_session=agent_session,
        include_memories=request.include_memories,
        include_tool_states=request.include_tool_states,
        is_auto=False,
    )
    return SnapshotResponse(
        id=snapshot.id,
        session_id=snapshot.session_id,
        name=snapshot.name,
        description=snapshot.description,
        created_at=snapshot.created_at,
        message_count=snapshot.message_count,
        is_auto=snapshot.is_auto,
    )


@router.get("/sessions/{session_id}/snapshots", response_model=list[SnapshotResponse])
async def list_snapshots(session_id: str, limit: int = 50, db=Depends(get_db)):
    svc = SnapshotService(db)
    snapshots = svc.list_snapshots(session_id=session_id, limit=limit)
    return [
        SnapshotResponse(
            id=s.id,
            session_id=s.session_id,
            name=s.name,
            description=s.description,
            created_at=s.created_at,
            message_count=s.message_count,
            is_auto=s.is_auto,
        )
        for s in snapshots
    ]


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(snapshot_id: str, db=Depends(get_db)):
    snapshot = db.get(AgentSnapshot, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    data = json.loads(snapshot.snapshot_data)
    return {
        "id": snapshot.id,
        "session_id": snapshot.session_id,
        "name": snapshot.name,
        "description": snapshot.description,
        "created_at": snapshot.created_at,
        "message_count": snapshot.message_count,
        "token_count": snapshot.token_count,
        "is_auto": snapshot.is_auto,
        "context_summary": snapshot.context_summary,
        "data": data,
    }


@router.post("/snapshots/{snapshot_id}/restore")
async def restore_snapshot(snapshot_id: str, db=Depends(get_db)):
    from common_lib.modules.agents.models.session_models import AgentSession

    svc = SnapshotService(db)
    try:
        data = svc.restore_snapshot(snapshot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    session_id = data["session_id"]
    agent_session = db.get(AgentSession, session_id)
    if not agent_session:
        raise HTTPException(status_code=404, detail="Original session not found")

    if data.get("history"):
        agent_session.history = data["history"]
    if data.get("state_variables"):
        agent_session.state_variables = data["state_variables"]
    if data.get("hints"):
        agent_session.hints = data["hints"]
    if data.get("facts"):
        agent_session.facts = data["facts"]
    if data.get("current_step"):
        agent_session.current_step = data["current_step"]
    if data.get("progress"):
        agent_session.progress = data["progress"]

    db.add(agent_session)
    db.commit()
    return {"status": "restored", "session_id": session_id}


@router.post("/snapshots/{snapshot_id}/replay")
async def replay_snapshot(snapshot_id: str, request: ReplayRequest, db=Depends(get_db)):
    svc = SnapshotService(db)
    new_session_id = request.new_session_name or f"replay_{uuid.uuid4().hex[:12]}"
    try:
        new_session = svc.replay_to_session(snapshot_id, new_session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "status": "replay_created",
        "original_snapshot": snapshot_id,
        "new_session_id": new_session.id,
    }


@router.delete("/snapshots/{snapshot_id}")
async def delete_snapshot(snapshot_id: str, db=Depends(get_db)):
    svc = SnapshotService(db)
    if not svc.delete_snapshot(snapshot_id):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"status": "deleted", "snapshot_id": snapshot_id}


@router.post("/sessions/{session_id}/snapshots/auto")
async def auto_snapshot(session_id: str, db=Depends(get_db)):
    from common_lib.modules.agents.models.session_models import AgentSession

    agent_session = db.get(AgentSession, session_id)
    if not agent_session:
        raise HTTPException(status_code=404, detail="Session not found")

    svc = SnapshotService(db)
    snapshot = svc.create_snapshot(
        session_id=session_id,
        name=f"Auto-{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        agent_session=agent_session,
        is_auto=True,
    )
    return {"status": "auto_snapshotted", "snapshot_id": snapshot.id}
