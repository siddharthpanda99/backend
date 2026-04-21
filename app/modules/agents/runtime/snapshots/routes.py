"""Snapshot API Routes"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Snapshots"])


def get_db_session():
    from app.modules.database.service.connection import Session
    from sqlmodel import Session as SQLSession

    with Session() as session:
        yield SQLSession(session)


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
    session_id: str,
    request: CreateSnapshotRequest,
    db=Depends(get_db_session),
):
    """Create a snapshot of current session state"""

    from app.modules.agents.runtime.session_models import AgentSession
    from app.modules.agents.runtime.snapshots import AgentSnapshot, SnapshotManager

    agent_session = db.get(AgentSession, session_id)
    if not agent_session:
        raise HTTPException(status_code=404, detail="Session not found")

    manager = SnapshotManager(db)
    snapshot = manager.create_snapshot(
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
async def list_snapshots(
    session_id: str,
    limit: int = 50,
    db=Depends(get_db_session),
):
    """List snapshots for a session"""

    from app.modules.agents.runtime.snapshots import AgentSnapshot, SnapshotManager

    manager = SnapshotManager(db)
    snapshots = manager.list_snapshots(session_id=session_id, limit=limit)

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
async def get_snapshot(
    snapshot_id: str,
    db=Depends(get_db_session),
):
    """Get snapshot details"""

    from app.modules.agents.runtime.snapshots import AgentSnapshot

    snapshot = db.get(AgentSnapshot, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    import json

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
async def restore_snapshot(
    snapshot_id: str,
    db=Depends(get_db_session),
):
    """Restore session state from snapshot"""

    from app.modules.agents.runtime.snapshots import AgentSnapshot, SnapshotManager
    from app.modules.agents.runtime.session_models import AgentSession

    manager = SnapshotManager(db)

    try:
        data = manager.restore_snapshot(snapshot_id)
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
async def replay_snapshot(
    snapshot_id: str,
    request: ReplayRequest,
    db=Depends(get_db_session),
):
    """Create new session by replaying snapshot (for debugging/auditing)"""

    from app.modules.agents.runtime.snapshots import AgentSnapshot, SnapshotManager
    import uuid

    manager = SnapshotManager(db)

    new_session_id = request.new_session_name or f"replay_{uuid.uuid4().hex[:12]}"

    try:
        new_session = manager.replay_to_session(snapshot_id, new_session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "status": "replay_created",
        "original_snapshot": snapshot_id,
        "new_session_id": new_session.id,
    }


@router.delete("/snapshots/{snapshot_id}")
async def delete_snapshot(
    snapshot_id: str,
    db=Depends(get_db_session),
):
    """Delete a snapshot"""

    from app.modules.agents.runtime.snapshots import SnapshotManager

    manager = SnapshotManager(db)
    deleted = manager.delete_snapshot(snapshot_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return {"status": "deleted", "snapshot_id": snapshot_id}


@router.post("/sessions/{session_id}/snapshots/auto")
async def auto_snapshot(
    session_id: str,
    db=Depends(get_db_session),
):
    """Create automatic checkpoint snapshot"""

    from app.modules.agents.runtime.session_models import AgentSession
    from app.modules.agents.runtime.snapshots import SnapshotManager

    agent_session = db.get(AgentSession, session_id)
    if not agent_session:
        raise HTTPException(status_code=404, detail="Session not found")

    manager = SnapshotManager(db)
    snapshot = manager.create_snapshot(
        session_id=session_id,
        name=f"Auto-{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        agent_session=agent_session,
        is_auto=True,
    )

    return {
        "status": "auto_snapshotted",
        "snapshot_id": snapshot.id,
    }
